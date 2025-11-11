from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from pharmacy_pos.common.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField('Nom', max_length=150, unique=True)
    code = models.CharField('Code', max_length=50, unique=True)
    description = models.TextField('Description', blank=True)

    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class DosageForm(TimeStampedModel):
    name = models.CharField('Nom', max_length=150, unique=True)

    class Meta:
        verbose_name = 'Forme galénique'
        verbose_name_plural = 'Formes galéniques'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Supplier(TimeStampedModel):
    name = models.CharField('Nom', max_length=255, unique=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Téléphone', max_length=50, blank=True)
    address = models.TextField('Adresse', blank=True)

    class Meta:
        verbose_name = 'Fournisseur'
        verbose_name_plural = 'Fournisseurs'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    name = models.CharField('Nom', max_length=255)
    barcode = models.CharField('Code-barres', max_length=100, unique=True)
    category = models.ForeignKey(
        Category,
        related_name='products',
        on_delete=models.PROTECT,
        verbose_name='Catégorie',
    )
    dosage_form = models.ForeignKey(
        DosageForm,
        related_name='products',
        on_delete=models.PROTECT,
        verbose_name='Forme galénique',
    )
    purchase_price = models.DecimalField(
        'Prix d\'achat',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    sale_price = models.DecimalField(
        'Prix de vente',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    stock_quantity = models.PositiveIntegerField('Quantité en stock', default=0)
    stock_threshold = models.PositiveIntegerField('Seuil d\'alerte', default=0)
    expiration_date = models.DateField('Date de péremption', null=True, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        related_name='products',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Fournisseur',
    )
    notes = models.TextField('Notes', blank=True)
    image = models.ImageField('Image', upload_to='products/', blank=True, null=True)

    class Meta:
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        ordering = ['name']
        unique_together = ('name', 'supplier')

    def __str__(self) -> str:
        return f'{self.name} ({self.barcode})'

    @property
    def is_below_threshold(self) -> bool:
        return self.stock_quantity <= self.stock_threshold

    def adjust_stock(
        self,
        quantity_delta: int,
        movement_type: 'StockMovement.MovementType',
        *,
        source: str = '',
        comment: str = '',
        movement_date: Optional[datetime] = None,
    ) -> Optional['StockMovement']:
        if quantity_delta == 0:
            return None

        if movement_type == StockMovement.MovementType.ADJUSTMENT:
            new_quantity = max(0, quantity_delta)
            movement_quantity = abs(new_quantity - self.stock_quantity)
            self.stock_quantity = new_quantity
        else:
            new_quantity = self.stock_quantity + quantity_delta
            if new_quantity < 0:
                raise ValueError('Quantité en stock insuffisante pour ce produit.')
            self.stock_quantity = new_quantity
            movement_quantity = abs(quantity_delta)

        self.save(update_fields=['stock_quantity', 'updated_at'])

        movement = StockMovement(
            product=self,
            movement_type=movement_type,
            quantity=movement_quantity,
            source=source,
            movement_date=movement_date or timezone.now(),
            comment=comment,
        )
        movement._skip_product_update = True  # type: ignore[attr-defined]
        movement.save()
        return movement


class StockMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        IN = 'in', 'Entrée'
        OUT = 'out', 'Sortie'
        ADJUSTMENT = 'adjustment', 'Ajustement'

    product = models.ForeignKey(
        Product,
        related_name='stock_movements',
        on_delete=models.CASCADE,
        verbose_name='Produit',
    )
    movement_type = models.CharField(
        'Type de mouvement',
        max_length=20,
        choices=MovementType.choices,
    )
    quantity = models.PositiveIntegerField('Quantité')
    source = models.CharField('Source', max_length=255, blank=True)
    movement_date = models.DateTimeField('Date du mouvement', default=timezone.now)
    comment = models.TextField('Commentaire', blank=True)

    class Meta:
        verbose_name = 'Mouvement de stock'
        verbose_name_plural = 'Mouvements de stock'
        ordering = ['-movement_date']

    def __str__(self) -> str:
        return f'{self.get_movement_type_display()} - {self.product.name} ({self.quantity})'

    def save(self, *args, **kwargs) -> None:
        is_new = self.pk is None
        skip_product_update = getattr(self, '_skip_product_update', False)
        if is_new and not skip_product_update:
            self.apply_to_product()
        super().save(*args, **kwargs)

    def apply_to_product(self) -> None:
        if self.movement_type == self.MovementType.ADJUSTMENT:
            self.product.stock_quantity = self.quantity
        elif self.movement_type == self.MovementType.IN:
            self.product.stock_quantity += self.quantity
        else:
            if self.product.stock_quantity < self.quantity:
                raise ValueError('Stock insuffisant pour ce mouvement.')
            self.product.stock_quantity -= self.quantity
        self.product.save(update_fields=['stock_quantity', 'updated_at'])
