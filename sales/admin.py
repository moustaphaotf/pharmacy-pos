from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import Customer, Invoice, Payment, Sale, SaleItem


class CustomerResource(resources.ModelResource):
    class Meta:
        model = Customer
        fields = ('id', 'name', 'email', 'phone', 'address', 'credit_balance', 'created_at', 'updated_at')
        export_order = ('id', 'name', 'email', 'phone', 'address', 'credit_balance', 'created_at', 'updated_at')


@admin.register(Customer)
class CustomerAdmin(ImportExportModelAdmin):
    resource_class = CustomerResource
    list_display = ('name', 'email', 'phone', 'credit_balance')
    search_fields = ('name', 'email', 'phone')


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    autocomplete_fields = ('product',)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


class SaleResource(resources.ModelResource):
    class Meta:
        model = Sale
        fields = (
            'id',
            'sale_date',
            'customer__name',
            'user__username',
            'subtotal',
            'tax_amount',
            'total_amount',
            'amount_paid',
            'balance_due',
            'payment_method',
            'status',
            'created_at',
            'updated_at',
        )
        export_order = fields


@admin.register(Sale)
class SaleAdmin(ImportExportModelAdmin):
    resource_class = SaleResource
    list_display = ('id', 'sale_date', 'customer', 'user', 'total_amount', 'amount_paid', 'status')
    list_filter = ('status', 'payment_method', 'sale_date')
    search_fields = ('id', 'customer__name', 'user__username')
    readonly_fields = ('subtotal', 'total_amount', 'amount_paid', 'balance_due', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('customer', 'user', 'sale_date', 'payment_method', 'status', 'notes')}),
        ('Finances', {'fields': ('subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'balance_due')}),
        ('Métadonnées', {'fields': ('created_at', 'updated_at')}),
    )
    inlines = [SaleItemInline, PaymentInline]


@admin.register(SaleItem)
class SaleItemAdmin(ImportExportModelAdmin):
    list_display = ('sale', 'product', 'quantity', 'unit_price', 'line_total')
    list_filter = ('product', 'sale')
    search_fields = ('sale__id', 'product__name', 'product__barcode')


@admin.register(Payment)
class PaymentAdmin(ImportExportModelAdmin):
    list_display = ('sale', 'amount', 'payment_method', 'payment_date')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('sale__id',)


@admin.register(Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
    list_display = ('invoice_number', 'sale', 'invoice_date', 'sent_email', 'sent_sms')
    list_filter = ('sent_email', 'sent_sms', 'invoice_date')
    search_fields = ('invoice_number', 'sale__id')
