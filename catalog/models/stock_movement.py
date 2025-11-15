"""
Modèle pour les mouvements de stock.
"""

from datetime import datetime
from typing import Optional

from django.db import models
from django.utils import timezone

from pharmacy_pos.common.models import TimeStampedModel

from .lot import Lot


class StockMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        IN = 'in', 'Entrée'
        OUT = 'out', 'Sortie'
        ADJUSTMENT = 'adjustment', 'Ajustement'

    lot = models.ForeignKey(
        Lot,
        related_name='stock_movements',
        on_delete=models.CASCADE,
        verbose_name='Lot',
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
        indexes = [
            models.Index(fields=['lot', '-movement_date']),
        ]

    def __str__(self) -> str:
        return f'{self.get_movement_type_display()} - {self.lot.product.name} ({self.quantity})'

    def save(self, *args, **kwargs) -> None:
        """
        Applique le mouvement au lot si c'est une nouvelle instance.
        """
        is_new = self.pk is None
        skip_lot_update = getattr(self, '_skip_lot_update', False)
        if is_new and not skip_lot_update:
            self.apply_to_lot()
        super().save(*args, **kwargs)

    def apply_to_lot(self) -> None:
        """
        Applique le mouvement au lot.
        """
        if self.movement_type == self.MovementType.ADJUSTMENT:
            # Pour un ajustement, on fixe la quantité restante
            self.lot.remaining_quantity = self.quantity
        elif self.movement_type == self.MovementType.IN:
            # Pour une entrée, on ajoute à la quantité restante
            self.lot.adjust_quantity(self.quantity)
        else:  # OUT
            # Pour une sortie, on soustrait de la quantité restante
            self.lot.adjust_quantity(-self.quantity)
        self.lot.save(update_fields=['remaining_quantity', 'updated_at'])

