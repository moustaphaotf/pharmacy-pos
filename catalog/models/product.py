"""
Modèle pour les produits.
"""

from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum

from pharmacy_pos.common.models import TimeStampedModel

from .category import Category, DosageForm
from .supplier import Supplier


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
    stock_threshold = models.PositiveIntegerField('Seuil d\'alerte', default=0)
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
    def purchase_price(self) -> Decimal:
        """
        Prix d'achat basé sur le dernier lot reçu.
        """
        from .lot import Lot
        
        last_lot = Lot.objects.filter(
            product=self,
            is_active=True,
        ).order_by('-created_at').first()
        
        if last_lot:
            return last_lot.purchase_price
        return Decimal('0.00')

    @property
    def sale_price(self) -> Decimal:
        """
        Prix de vente basé sur le dernier lot reçu.
        """
        from .lot import Lot
        
        last_lot = Lot.objects.filter(
            product=self,
            is_active=True,
        ).order_by('-created_at').first()
        
        if last_lot:
            return last_lot.sale_price
        return Decimal('0.00')

    @property
    def total_stock(self) -> int:
        """
        Quantité totale en stock (non expirée).
        """
        from .lot import Lot
        
        today = date.today()
        return Lot.objects.filter(
            product=self,
            is_active=True,
            expiration_date__gt=today,
        ).aggregate(total=Sum('remaining_quantity'))['total'] or 0

    @property
    def total_expired_stock(self) -> int:
        """
        Quantité totale expirée mais pas encore sortie du stock.
        """
        from .lot import Lot
        
        today = date.today()
        return Lot.objects.filter(
            product=self,
            is_active=True,
            expiration_date__lte=today,
            remaining_quantity__gt=0,
        ).aggregate(total=Sum('remaining_quantity'))['total'] or 0

    @property
    def is_below_threshold(self) -> bool:
        """
        Vérifie si le stock total est en dessous du seuil d'alerte.
        """
        return self.total_stock <= self.stock_threshold

