"""
Modèle pour les clients.
"""

from decimal import Decimal

from django.db import models

from pharmacy_pos.common.models import TimeStampedModel


class Customer(TimeStampedModel):
    name = models.CharField('Nom', max_length=255)
    phone = models.CharField('Téléphone', max_length=50, blank=True)
    email = models.EmailField('Email', blank=True)
    address = models.TextField('Adresse', blank=True)
    credit_balance = models.DecimalField(
        'Solde crédit',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name

