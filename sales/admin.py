from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
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
    readonly_fields = ('unit_price', 'line_total')
    min_num = 1
    validate_min = True
    fields = ('product', 'quantity', 'unit_price', 'line_total')


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
    readonly_fields = ('user', 'subtotal', 'total_amount', 'amount_paid', 'balance_due', 'created_at', 'updated_at')
    fieldsets = (
        (_('Général'), {'fields': ('customer', 'sale_date', 'payment_method', 'status', 'notes')}),
        (_('Finances'), {'fields': ('subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'balance_due')}),
        (_('Métadonnées'), {'fields': ('user', 'created_at', 'updated_at')}),
    )
    inlines = [SaleItemInline, PaymentInline]

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                (_('Général'), {'fields': ('customer', 'sale_date', 'payment_method', 'status', 'notes')}),
            )
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is None:
            readonly.append('tax_amount')
        return readonly

    def save_model(self, request, obj, form, change):
        if not obj.user_id:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['customer'].required = True
        return form


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
