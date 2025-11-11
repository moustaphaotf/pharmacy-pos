from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    Category,
    Customer,
    DosageForm,
    Invoice,
    Payment,
    Product,
    Sale,
    SaleItem,
    StockMovement,
    Supplier,
    User,
)


class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role information', {'fields': ('role',)}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_active')
    list_filter = BaseUserAdmin.list_filter + ('role',)
    search_fields = BaseUserAdmin.search_fields + ('role',)


admin.site.register(User, UserAdmin)


class CategoryResource(resources.ModelResource):
    class Meta:
        model = Category
        fields = ('id', 'name', 'code', 'description', 'created_at', 'updated_at')
        export_order = ('id', 'name', 'code', 'description', 'created_at', 'updated_at')


@admin.register(Category)
class CategoryAdmin(ImportExportModelAdmin):
    resource_class = CategoryResource
    list_display = ('name', 'code', 'description')
    search_fields = ('name', 'code')


@admin.register(DosageForm)
class DosageFormAdmin(ImportExportModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class SupplierResource(resources.ModelResource):
    class Meta:
        model = Supplier
        fields = ('id', 'name', 'email', 'phone', 'address', 'created_at', 'updated_at')
        export_order = ('id', 'name', 'email', 'phone', 'address', 'created_at', 'updated_at')


@admin.register(Supplier)
class SupplierAdmin(ImportExportModelAdmin):
    resource_class = SupplierResource
    list_display = ('name', 'email', 'phone')
    search_fields = ('name', 'email', 'phone')


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


class ProductResource(resources.ModelResource):
    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'barcode',
            'category__name',
            'dosage_form__name',
            'purchase_price',
            'sale_price',
            'stock_quantity',
            'stock_threshold',
            'expiration_date',
            'supplier__name',
            'created_at',
            'updated_at',
        )
        export_order = fields


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    resource_class = ProductResource
    list_display = (
        'name',
        'barcode',
        'category',
        'dosage_form',
        'sale_price',
        'stock_quantity',
        'stock_threshold',
        'is_below_threshold',
    )
    list_filter = ('category', 'dosage_form', 'supplier')
    search_fields = ('name', 'barcode')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'barcode', 'category', 'dosage_form', 'supplier', 'image')}),
        ('Stock & pricing', {'fields': ('purchase_price', 'sale_price', 'stock_quantity', 'stock_threshold', 'expiration_date')}),
        ('Additional', {'fields': ('notes', 'created_at', 'updated_at')}),
    )


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
        ('Financials', {'fields': ('subtotal', 'tax_amount', 'total_amount', 'amount_paid', 'balance_due')}),
        ('Metadata', {'fields': ('created_at', 'updated_at')}),
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


@admin.register(StockMovement)
class StockMovementAdmin(ImportExportModelAdmin):
    list_display = ('product', 'movement_type', 'quantity', 'movement_date', 'source')
    list_filter = ('movement_type', 'movement_date')
    search_fields = ('product__name', 'source')
