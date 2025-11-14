"""
Modèle pour les factures.
"""

import uuid

from django.db import models
from django.utils import timezone

from pharmacy_pos.common.models import TimeStampedModel

from .sale import Sale


class Invoice(TimeStampedModel):
    sale = models.OneToOneField(
        Sale,
        related_name='invoice',
        on_delete=models.CASCADE,
        verbose_name='Vente',
    )
    invoice_number = models.CharField('Numéro de facture', max_length=100, unique=True)
    invoice_date = models.DateTimeField('Date de facture', default=timezone.now)
    pdf = models.FileField('Fichier PDF', upload_to='invoices/', blank=True, null=True)
    sent_email = models.BooleanField('Envoyée par email', default=False)
    sent_sms = models.BooleanField('Envoyée par SMS', default=False)

    class Meta:
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-invoice_date']

    def __str__(self) -> str:
        return f'Facture {self.invoice_number}'

    def save(self, *args, **kwargs) -> None:
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_invoice_number() -> str:
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f'INV-{timestamp}-{random_suffix}'

