"""
Modèles pour les fournisseurs et commandes d'achat.
"""

from django.db import models
from django.utils import timezone

from pharmacy_pos.common.models import TimeStampedModel


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


class PurchaseOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        RECEIVED = 'received', 'Réceptionnée'
        CANCELLED = 'cancelled', 'Annulée'

    supplier = models.ForeignKey(
        Supplier,
        related_name='purchase_orders',
        on_delete=models.PROTECT,
        verbose_name='Fournisseur',
    )
    order_date = models.DateTimeField('Date de commande', default=timezone.now)
    receipt_date = models.DateTimeField('Date de réception', null=True, blank=True)
    status = models.CharField(
        'Statut',
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField('Notes', blank=True)

    class Meta:
        verbose_name = 'Commande d\'achat'
        verbose_name_plural = 'Commandes d\'achat'
        ordering = ['-order_date']

    def __str__(self) -> str:
        return f'Commande #{self.pk or "—"} - {self.supplier.name}'

