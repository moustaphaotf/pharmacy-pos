"""
Modèles pour les lignes de vente et la traçabilité par lot.
"""

from decimal import Decimal
from typing import List, Tuple

from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.utils import timezone

from catalog.models import Lot, StockMovement
from pharmacy_pos.common.models import TimeStampedModel

from .sale import Sale


class SaleItem(TimeStampedModel):
    sale = models.ForeignKey(
        Sale,
        related_name='items',
        on_delete=models.CASCADE,
        verbose_name='Vente',
    )
    product = models.ForeignKey(
        'catalog.Product',
        related_name='sale_items',
        on_delete=models.PROTECT,
        verbose_name='Produit',
    )
    quantity = models.PositiveIntegerField(
        'Quantité',
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        'Prix unitaire',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    line_total = models.DecimalField(
        'Total ligne',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    class Meta:
        verbose_name = 'Ligne de vente'
        verbose_name_plural = 'Lignes de vente'
        unique_together = ('sale', 'product')

    def __str__(self) -> str:
        return f'{self.product.name} x {self.quantity}'

    def _get_lots_for_sale(self, quantity_needed: int) -> List[Tuple[Lot, int]]:
        """
        Récupère les lots disponibles pour la vente selon la logique FEFO.
        Retourne une liste de tuples (lot, quantité_prélevée).
        """
        from datetime import date
        
        today = date.today()
        
        # Récupère les lots actifs, non expirés, avec stock disponible
        # Triés par date d'expiration croissante (FEFO)
        available_lots = Lot.objects.filter(
            product=self.product,
            is_active=True,
            expiration_date__gt=today,
            remaining_quantity__gt=0,
        ).order_by('expiration_date', 'created_at')
        
        lots_to_use = []
        remaining_quantity = quantity_needed
        
        for lot in available_lots:
            if remaining_quantity <= 0:
                break
            
            quantity_from_lot = min(lot.remaining_quantity, remaining_quantity)
            lots_to_use.append((lot, quantity_from_lot))
            remaining_quantity -= quantity_from_lot
        
        if remaining_quantity > 0:
            raise ValueError(
                f'Stock insuffisant pour {self.product.name}. '
                f'Quantité demandée: {quantity_needed}, '
                f'Quantité disponible: {quantity_needed - remaining_quantity}'
            )
        
        return lots_to_use

    def _create_sale_item_lots(self, lots_to_use: List[Tuple[Lot, int]]) -> None:
        """
        Crée les SaleItemLot et met à jour les lots.
        """
        for lot, quantity in lots_to_use:
            # Crée le SaleItemLot
            SaleItemLot.objects.create(
                sale_item=self,
                lot=lot,
                quantity=quantity,
                unit_price=lot.sale_price,
            )
            
            # Met à jour la quantité restante du lot
            lot.adjust_quantity(-quantity)
            
            # Crée le mouvement de stock
            StockMovement.objects.create(
                lot=lot,
                movement_type=StockMovement.MovementType.OUT,
                quantity=quantity,
                source=f'Vente #{self.sale_id}',
                comment=f'Ligne de vente {self.pk}',
                movement_date=self.sale.sale_date,
            )

    def _remove_sale_item_lots(self) -> None:
        """
        Supprime les SaleItemLot et restaure les lots.
        """
        sale_item_lots = SaleItemLot.objects.filter(sale_item=self)
        
        for sale_item_lot in sale_item_lots:
            lot = sale_item_lot.lot
            quantity = sale_item_lot.quantity
            
            # Restaure la quantité du lot
            lot.adjust_quantity(quantity)
            
            # Crée un mouvement de stock d'entrée
            StockMovement.objects.create(
                lot=lot,
                movement_type=StockMovement.MovementType.IN,
                quantity=quantity,
                source=f'Vente #{self.sale_id} (annulation)',
                comment=f'Suppression ligne de vente {self.pk}',
                movement_date=self.sale.sale_date,
            )
        
        # Supprime les SaleItemLot
        sale_item_lots.delete()

    @transaction.atomic
    def save(self, *args, **kwargs) -> None:
        is_new = self.pk is None
        previous_quantity = 0
        
        # Détermine le prix unitaire si non fourni
        if not self.unit_price:
            # Utilise le prix du dernier lot (pour affichage)
            # Mais les SaleItemLot utiliseront le prix réel de chaque lot
            self.unit_price = self.product.sale_price
        
        if not is_new:
            previous_quantity = SaleItem.objects.only('quantity').get(pk=self.pk).quantity
        
        # Calcule le total de la ligne
        self.line_total = (self.unit_price or Decimal('0.00')) * self.quantity
        
        # Sauvegarde d'abord pour avoir un PK
        super().save(*args, **kwargs)
        
        # Gère les lots selon la différence de quantité
        quantity_diff = self.quantity - previous_quantity
        
        if is_new:
            # Nouvelle ligne : crée les SaleItemLot
            if self.quantity > 0:
                lots_to_use = self._get_lots_for_sale(self.quantity)
                self._create_sale_item_lots(lots_to_use)
        elif quantity_diff != 0:
            # Modification : supprime les anciens et recrée
            self._remove_sale_item_lots()
            if self.quantity > 0:
                lots_to_use = self._get_lots_for_sale(self.quantity)
                self._create_sale_item_lots(lots_to_use)
        
        # Met à jour les totaux de la vente
        self.sale.update_totals_from_items()

    @transaction.atomic
    def delete(self, *args, **kwargs) -> None:
        # Restaure les lots avant de supprimer
        self._remove_sale_item_lots()
        sale = self.sale
        super().delete(*args, **kwargs)
        sale.update_totals_from_items()


class SaleItemLot(TimeStampedModel):
    """
    Traçabilité des lots utilisés dans une ligne de vente.
    """
    sale_item = models.ForeignKey(
        SaleItem,
        related_name='lot_items',
        on_delete=models.CASCADE,
        verbose_name='Ligne de vente',
    )
    lot = models.ForeignKey(
        Lot,
        related_name='sale_item_lots',
        on_delete=models.PROTECT,
        verbose_name='Lot',
    )
    quantity = models.PositiveIntegerField(
        'Quantité',
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        'Prix unitaire',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    class Meta:
        verbose_name = 'Lot de ligne de vente'
        verbose_name_plural = 'Lots de lignes de vente'
        unique_together = ('sale_item', 'lot')

    def __str__(self) -> str:
        return f'{self.sale_item.product.name} - Lot {self.lot.batch_number or self.lot.pk} x {self.quantity}'

