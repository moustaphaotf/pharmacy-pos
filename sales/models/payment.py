"""
Modèle pour les paiements.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from pharmacy_pos.common.models import TimeStampedModel

from .sale import Sale


class Payment(TimeStampedModel):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Espèces'
        CARD = 'card', 'Carte'
        MOBILE_MONEY = 'mobile_money', 'Mobile Money'
        BANK_TRANSFER = 'bank_transfer', 'Virement bancaire'
        OTHER = 'other', 'Autre'

    sale = models.ForeignKey(
        Sale,
        related_name='payments',
        on_delete=models.CASCADE,
        verbose_name='Vente',
    )
    amount = models.DecimalField(
        'Montant',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    payment_method = models.CharField(
        'Mode de paiement',
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    payment_date = models.DateTimeField('Date de paiement', default=timezone.now)

    class Meta:
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-payment_date']

    def __str__(self) -> str:
        return f'Paiement {self.amount} pour la vente #{self.sale_id}'

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        self.sale.refresh_payment_summary()

    def delete(self, *args, **kwargs) -> None:
        sale = self.sale
        super().delete(*args, **kwargs)
        sale.refresh_payment_summary()

