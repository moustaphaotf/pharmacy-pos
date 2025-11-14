"""
Modèle pour les lots de produits.
"""

from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from pharmacy_pos.common.models import TimeStampedModel

from .product import Product
from .supplier import PurchaseOrder

# Import différé pour éviter les imports circulaires
# StockMovement est importé dans les méthodes qui en ont besoin


class Lot(TimeStampedModel):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        related_name='lots',
        on_delete=models.PROTECT,
        verbose_name='Commande d\'achat',
    )
    product = models.ForeignKey(
        Product,
        related_name='lots',
        on_delete=models.PROTECT,
        verbose_name='Produit',
    )
    quantity = models.PositiveIntegerField(
        'Quantité initiale',
        validators=[MinValueValidator(1)],
    )
    remaining_quantity = models.PositiveIntegerField(
        'Quantité restante',
        validators=[MinValueValidator(0)],
    )
    expiration_date = models.DateField('Date de péremption')
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
    batch_number = models.CharField('Numéro de lot', max_length=100, blank=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Lot'
        verbose_name_plural = 'Lots'
        ordering = ['expiration_date', 'created_at']
        indexes = [
            models.Index(fields=['product', 'expiration_date', 'is_active']),
            models.Index(fields=['is_active', 'expiration_date']),
        ]

    def __str__(self) -> str:
        batch_info = f' - Lot {self.batch_number}' if self.batch_number else ''
        return f'{self.product.name}{batch_info} (Exp: {self.expiration_date})'

    def save(self, *args, **kwargs) -> None:
        """
        Initialise remaining_quantity à quantity si c'est une nouvelle instance.
        """
        if self.pk is None:
            self.remaining_quantity = self.quantity
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        """
        Vérifie si le lot est expiré.
        """
        return self.expiration_date <= date.today()

    @property
    def is_exhausted(self) -> bool:
        """
        Vérifie si le lot est épuisé (remaining_quantity = 0).
        """
        return self.remaining_quantity == 0

    def adjust_quantity(self, quantity_delta: int) -> None:
        """
        Ajuste la quantité restante du lot.
        """
        new_quantity = self.remaining_quantity + quantity_delta
        if new_quantity < 0:
            raise ValueError(
                f'Quantité insuffisante dans le lot. '
                f'Quantité restante: {self.remaining_quantity}, '
                f'Demandée: {abs(quantity_delta)}'
            )
        if new_quantity > self.quantity:
            raise ValueError(
                f'La quantité restante ne peut pas dépasser la quantité initiale. '
                f'Quantité initiale: {self.quantity}, '
                f'Tentative: {new_quantity}'
            )
        self.remaining_quantity = new_quantity
        self.save(update_fields=['remaining_quantity', 'updated_at'])

