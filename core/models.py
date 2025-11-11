from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'admin', 'Administrator'
        CASHIER = 'cashier', 'Cashier'
        PHARMACIST = 'pharmacist', 'Pharmacist'

    role = models.CharField(
        max_length=20,
        choices=Roles.choices,
        default=Roles.CASHIER,
    )

    def __str__(self) -> str:
        return f'{self.get_full_name() or self.username} ({self.get_role_display()})'


class Category(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class DosageForm(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = 'Dosage form'
        verbose_name_plural = 'Dosage forms'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Customer(TimeStampedModel):
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    credit_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(Category, related_name='products', on_delete=models.PROTECT)
    dosage_form = models.ForeignKey(
        DosageForm,
        related_name='products',
        on_delete=models.PROTECT,
    )
    purchase_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    sale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    stock_threshold = models.PositiveIntegerField(default=0)
    expiration_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey(
        Supplier,
        related_name='products',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    notes = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    class Meta:
        ordering = ['name']
        unique_together = ('name', 'supplier')

    def __str__(self) -> str:
        return f'{self.name} ({self.barcode})'

    @property
    def is_below_threshold(self) -> bool:
        return self.stock_quantity <= self.stock_threshold

    def adjust_stock(
        self,
        quantity_delta: int,
        movement_type: 'StockMovement.MovementType',
        *,
        source: str = '',
        comment: str = '',
        movement_date: Optional[datetime] = None,
    ) -> Optional['StockMovement']:
        if quantity_delta == 0:
            return None

        if movement_type == StockMovement.MovementType.ADJUSTMENT:
            new_quantity = max(0, quantity_delta)
            movement_quantity = abs(new_quantity - self.stock_quantity)
            self.stock_quantity = new_quantity
        else:
            new_quantity = self.stock_quantity + quantity_delta
            if new_quantity < 0:
                raise ValueError('Insufficient stock quantity for product.')
            self.stock_quantity = new_quantity
            movement_quantity = abs(quantity_delta)

        self.save(update_fields=['stock_quantity', 'updated_at'])

        movement = StockMovement(
            product=self,
            movement_type=movement_type,
            quantity=movement_quantity,
            source=source,
            movement_date=movement_date or timezone.now(),
            comment=comment,
        )
        movement._skip_product_update = True  # type: ignore[attr-defined]
        movement.save()
        return movement


class Sale(TimeStampedModel):
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Cash'
        CARD = 'card', 'Card'
        CREDIT = 'credit', 'Credit'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PAID = 'paid', 'Paid'
        PARTIAL = 'partial', 'Partial'

    customer = models.ForeignKey(
        Customer,
        related_name='sales',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    sale_date = models.DateTimeField(default=timezone.now)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='sales',
        on_delete=models.PROTECT,
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    balance_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-sale_date']

    def __str__(self) -> str:
        return f'Sale #{self.pk or "—"}'

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
        if not customer_id:
            return
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return
        credit_total = (
            customer.sales.filter(
                payment_method=Sale.PaymentMethod.CREDIT,
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


class SaleItem(TimeStampedModel):
    sale = models.ForeignKey(
        Sale,
        related_name='items',
        on_delete=models.CASCADE,
    )
    product = models.ForeignKey(
        Product,
        related_name='sale_items',
        on_delete=models.PROTECT,
    )
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    class Meta:
        unique_together = ('sale', 'product')

    def __str__(self) -> str:
        return f'{self.product.name} x {self.quantity}'

    def save(self, *args, **kwargs) -> None:
        is_new = self.pk is None
        previous_quantity = 0
        if not self.unit_price:
            self.unit_price = self.product.sale_price

        if not is_new:
            previous_quantity = SaleItem.objects.only('quantity').get(pk=self.pk).quantity

        self.line_total = (self.unit_price or Decimal('0.00')) * self.quantity
        super().save(*args, **kwargs)

        quantity_diff = self.quantity - previous_quantity
        if quantity_diff != 0:
            self.product.adjust_stock(
                quantity_delta=-quantity_diff,
                movement_type=StockMovement.MovementType.OUT,
                source=f'Sale #{self.sale_id}',
                comment=f'Sale item {self.pk}',
                movement_date=self.sale.sale_date,
            )

        self.sale.update_totals_from_items()

    def delete(self, *args, **kwargs) -> None:
        product = self.product
        sale = self.sale
        quantity = self.quantity
        super().delete(*args, **kwargs)
        product.adjust_stock(
            quantity_delta=quantity,
            movement_type=StockMovement.MovementType.IN,
            source=f'Sale #{sale.pk} (reversal)',
            comment=f'Removed sale item',
            movement_date=sale.sale_date,
        )
        sale.update_totals_from_items()


class Invoice(TimeStampedModel):
    sale = models.OneToOneField(
        Sale,
        related_name='invoice',
        on_delete=models.CASCADE,
    )
    invoice_number = models.CharField(max_length=100, unique=True)
    invoice_date = models.DateTimeField(default=timezone.now)
    pdf = models.FileField(upload_to='invoices/', blank=True, null=True)
    sent_email = models.BooleanField(default=False)
    sent_sms = models.BooleanField(default=False)

    class Meta:
        ordering = ['-invoice_date']

    def __str__(self) -> str:
        return f'Invoice {self.invoice_number}'

    def save(self, *args, **kwargs) -> None:
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_invoice_number() -> str:
        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f'INV-{timestamp}-{random_suffix}'


class Payment(TimeStampedModel):
    sale = models.ForeignKey(
        Sale,
        related_name='payments',
        on_delete=models.CASCADE,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    payment_method = models.CharField(
        max_length=20,
        choices=Sale.PaymentMethod.choices,
    )
    payment_date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self) -> str:
        return f'Payment {self.amount} for Sale #{self.sale_id}'

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        self.sale.refresh_payment_summary()

    def delete(self, *args, **kwargs) -> None:
        sale = self.sale
        super().delete(*args, **kwargs)
        sale.refresh_payment_summary()


class StockMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        IN = 'in', 'In'
        OUT = 'out', 'Out'
        ADJUSTMENT = 'adjustment', 'Adjustment'

    product = models.ForeignKey(
        Product,
        related_name='stock_movements',
        on_delete=models.CASCADE,
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )
    quantity = models.PositiveIntegerField()
    source = models.CharField(max_length=255, blank=True)
    movement_date = models.DateTimeField(default=timezone.now)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ['-movement_date']

    def __str__(self) -> str:
        return f'{self.get_movement_type_display()} - {self.product.name} ({self.quantity})'

    def save(self, *args, **kwargs) -> None:
        is_new = self.pk is None
        skip_product_update = getattr(self, '_skip_product_update', False)
        if is_new and not skip_product_update:
            self.apply_to_product()
        super().save(*args, **kwargs)

    def apply_to_product(self) -> None:
        if self.movement_type == self.MovementType.ADJUSTMENT:
            self.product.stock_quantity = self.quantity
        elif self.movement_type == self.MovementType.IN:
            self.product.stock_quantity += self.quantity
        else:
            if self.product.stock_quantity < self.quantity:
                raise ValueError('Insufficient stock for this movement.')
            self.product.stock_quantity -= self.quantity
        self.product.save(update_fields=['stock_quantity', 'updated_at'])
