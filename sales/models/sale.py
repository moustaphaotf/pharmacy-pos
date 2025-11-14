"""
Modèle pour les ventes.
"""

from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from pharmacy_pos.common.models import TimeStampedModel

from .customer import Customer


class Sale(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Brouillon'
        PAID = 'paid', 'Payée'
        PARTIAL = 'partial', 'Partielle'

    customer = models.ForeignKey(
        Customer,
        related_name='sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Client',
    )
    sale_date = models.DateTimeField('Date de vente', default=timezone.now)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='sales',
        on_delete=models.PROTECT,
        verbose_name='Utilisateur',
    )
    subtotal = models.DecimalField(
        'Sous-total',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    tax_amount = models.DecimalField(
        'Taxe',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_amount = models.DecimalField(
        'Total TTC',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    amount_paid = models.DecimalField(
        'Montant payé',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[],
    )
    balance_due = models.DecimalField(
        'Solde restant',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(
        'Statut',
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField('Notes', blank=True)

    class Meta:
        verbose_name = 'Vente'
        verbose_name_plural = 'Ventes'
        ordering = ['-sale_date']

    def __str__(self) -> str:
        return f'Vente #{self.pk or "—"}'

    def update_totals_from_items(self) -> None:
        subtotal = self.items.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
        self.subtotal = subtotal
        self.total_amount = subtotal + self.tax_amount
        self.balance_due = self.total_amount - self.amount_paid
        self.status = self.compute_status()
        self.save(update_fields=['subtotal', 'total_amount', 'balance_due', 'status', 'updated_at'])

    def compute_status(self) -> str:
        if self.amount_paid >= self.total_amount:
            return self.Status.PAID
        if self.amount_paid > 0:
            return self.Status.PARTIAL
        return self.Status.DRAFT

    def refresh_payment_summary(self) -> None:
        payments_total = self.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        self.amount_paid = payments_total
        self.balance_due = self.total_amount - payments_total
        self.status = self.compute_status()
        self.save(update_fields=['amount_paid', 'balance_due', 'status', 'updated_at'])

    def update_customer_credit_balance(self) -> None:
        self.recalculate_customer_credit(self.customer_id)

    @staticmethod
    def recalculate_customer_credit(customer_id: Optional[int]) -> None:
        """
        Recalcule le solde crédit du client en additionnant tous les balance_due > 0.
        Une vente à crédit est simplement une vente avec un solde restant à payer.
        """
        if not customer_id:
            return
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return
        credit_total = (
            customer.sales.filter(
                balance_due__gt=Decimal('0.00'),
            ).aggregate(total=Sum('balance_due'))['total']
            or Decimal('0.00')
        )
        customer.credit_balance = credit_total
        customer.save(update_fields=['credit_balance', 'updated_at'])

    def save(self, *args, **kwargs) -> None:
        previous_customer_id: Optional[int] = None
        if self.pk:
            previous_customer_id = Sale.objects.only('customer_id').get(pk=self.pk).customer_id
        self.subtotal = self.subtotal or Decimal('0.00')
        self.tax_amount = self.tax_amount or Decimal('0.00')
        self.amount_paid = self.amount_paid or Decimal('0.00')
        self.total_amount = self.subtotal + self.tax_amount
        self.balance_due = self.total_amount - self.amount_paid
        self.status = self.compute_status()
        super().save(*args, **kwargs)
        if previous_customer_id and previous_customer_id != self.customer_id:
            self.recalculate_customer_credit(previous_customer_id)
        self.update_customer_credit_balance()

