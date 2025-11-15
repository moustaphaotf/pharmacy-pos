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
    class DiscountType(models.TextChoices):
        AMOUNT = 'amount', 'Montant'
        PERCENTAGE = 'percentage', 'Pourcentage'

    discount_type = models.CharField(
        'Type de remise',
        max_length=20,
        choices=DiscountType.choices,
        default=DiscountType.AMOUNT,
    )
    discount_value = models.DecimalField(
        'Valeur de la remise',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Montant ou pourcentage de la remise selon le type',
    )
    # Champ legacy pour compatibilité (sera supprimé après migration)
    discount_amount = models.DecimalField(
        'Remise (legacy)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Montant de la remise appliquée à la vente (deprecated)',
        editable=False,
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

    def get_discount_display(self) -> str:
        """
        Retourne la remise formatée pour l'affichage.
        Ex: "10% (100.00 GNF)" ou "100.00 GNF"
        """
        if self.discount_value == 0:
            return '0.00 GNF'
        
        if self.discount_type == self.DiscountType.PERCENTAGE:
            # Calculer le montant réel pour l'affichage
            # On utilise le subtotal actuel pour le calcul
            subtotal = self.items.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
            discount_amount = self.calculate_discount_amount(subtotal)
            return f"{self.discount_value}% ({discount_amount:.2f} GNF)"
        else:
            return f"{self.discount_value:.2f} GNF"

    def calculate_discount_amount(self, subtotal: Decimal) -> Decimal:
        """
        Calcule le montant réel de la remise selon le type.
        """
        if self.discount_type == self.DiscountType.PERCENTAGE:
            return subtotal * (self.discount_value / Decimal('100.00'))
        else:  # AMOUNT
            return self.discount_value

    def update_totals_from_items(self) -> None:
        subtotal = self.items.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
        discount_amount = self.calculate_discount_amount(subtotal)
        self.subtotal = subtotal - discount_amount  # Sous-total après remise
        self.total_amount = self.subtotal + self.tax_amount
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
        self.discount_amount = self.discount_amount or Decimal('0.00')
        self.amount_paid = self.amount_paid or Decimal('0.00')
        # Le subtotal est déjà calculé après remise dans update_totals_from_items
        # Sinon, on recalcule ici (seulement si la vente existe déjà en base)
        if not hasattr(self, '_totals_updated') and self.pk:
            items_subtotal = self.items.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
            self.subtotal = items_subtotal - self.discount_amount
        self.total_amount = self.subtotal + self.tax_amount
        self.balance_due = self.total_amount - self.amount_paid
        self.status = self.compute_status()
        super().save(*args, **kwargs)
        if previous_customer_id and previous_customer_id != self.customer_id:
            self.recalculate_customer_credit(previous_customer_id)
        self.update_customer_credit_balance()

