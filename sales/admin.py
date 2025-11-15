from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import Customer, Invoice, Payment, Sale, SaleItem, SaleItemLot


class CustomerResource(resources.ModelResource):
    class Meta:
        model = Customer
        fields = ('id', 'name', 'email', 'phone', 'address', 'credit_balance', 'created_at', 'updated_at')
        export_order = ('id', 'name', 'email', 'phone', 'address', 'credit_balance', 'created_at', 'updated_at')


@admin.register(Customer)
class CustomerAdmin(ImportExportModelAdmin):
    resource_class = CustomerResource
    list_display = ('name', 'email', 'phone', 'credit_balance', 'is_anonymous')
    list_filter = ('is_anonymous',)
    search_fields = ('name', 'email', 'phone')
    
    def get_queryset(self, request):
        """
        Par défaut, exclure les clients anonymes de la liste.
        Les admins peuvent les voir en utilisant le filtre is_anonymous.
        """
        qs = super().get_queryset(request)
        # Si le filtre is_anonymous n'est pas activé, exclure les anonymes
        if 'is_anonymous__exact' not in request.GET:
            qs = qs.filter(is_anonymous=False)
        return qs


class SaleItemLotInline(admin.TabularInline):
    model = SaleItemLot
    extra = 0
    readonly_fields = ('lot', 'quantity', 'unit_price')
    can_delete = False
    fields = ('lot', 'quantity', 'unit_price')


# Inlines désactivés car React gère tout le formulaire
# class SaleItemInline(admin.TabularInline):
#     model = SaleItem
#     extra = 0
#     autocomplete_fields = ('product',)
#     readonly_fields = ('unit_price', 'line_total')
#     min_num = 0
#     validate_min = False
#     fields = ('product', 'quantity', 'unit_price', 'line_total')

# class PaymentInline(admin.TabularInline):
#     model = Payment
#     extra = 0


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
            'status',
            'created_at',
            'updated_at',
        )
        export_order = fields


@admin.register(Sale)
class SaleAdmin(ImportExportModelAdmin):
    resource_class = SaleResource
    list_display = ('reference', 'sale_date', 'customer', 'get_discount_display', 'total_amount', 'amount_paid', 'balance_due', 'status')
    list_filter = ('status', 'sale_date')
    search_fields = ('reference', 'id', 'customer__name', 'user__username')
    readonly_fields = ('reference', 'user', 'subtotal', 'get_discount_display', 'total_amount', 'amount_paid', 'balance_due', 'created_at', 'updated_at')
    fieldsets = (
        (_('Général'), {'fields': ('reference', 'customer', 'sale_date', 'notes')}),
        (_('Finances'), {'fields': ('subtotal', 'discount_type', 'discount_value', 'get_discount_display', 'tax_amount', 'total_amount', 'amount_paid', 'balance_due')}),
        (_('Métadonnées'), {'fields': ('user', 'status', 'created_at', 'updated_at')}),
    )
    
    def get_discount_display(self, obj):
        """Affiche la remise formatée dans la liste et les détails."""
        return obj.get_discount_display()
    get_discount_display.short_description = 'Remise'
    # Inlines désactivés car React gère tout
    # inlines = [SaleItemInline, PaymentInline]
    
    # Désactiver les onglets pour cette vue (via le template)
    changeform_format = 'single'
    
    # Utiliser le template React pour toutes les ventes (ajout et modification)
    change_form_template = 'admin/sales/sale/change_form_react.html'

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                (_('Général'), {'fields': ('customer', 'sale_date', 'status', 'notes')}),
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
    
    def get_changeform_initial_data(self, request):
        """
        Initialise les données par défaut pour une nouvelle vente.
        """
        initial = super().get_changeform_initial_data(request)
        from django.utils import timezone
        initial['sale_date'] = timezone.now()
        return initial


@admin.register(SaleItem)
class SaleItemAdmin(ImportExportModelAdmin):
    list_display = ('sale', 'product', 'quantity', 'unit_price', 'line_total')
    list_filter = ('product', 'sale')
    search_fields = ('sale__id', 'product__name', 'product__barcode')
    inlines = [SaleItemLotInline]


@admin.register(SaleItemLot)
class SaleItemLotAdmin(ImportExportModelAdmin):
    list_display = ('sale_item', 'lot', 'quantity', 'unit_price')
    list_filter = ('lot__product', 'lot__expiration_date')
    search_fields = ('sale_item__product__name', 'lot__batch_number')
    readonly_fields = ('created_at', 'updated_at')


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
