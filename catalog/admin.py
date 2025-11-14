from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    Category,
    DosageForm,
    Lot,
    Product,
    PurchaseOrder,
    StockMovement,
    Supplier,
)


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


class ProductResource(resources.ModelResource):
    class Meta:
        model = Product
        fields = (
            'id',
            'name',
            'barcode',
            'category__name',
            'dosage_form__name',
            'stock_threshold',
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
        'total_stock',
        'total_expired_stock',
        'stock_threshold',
        'is_below_threshold',
    )
    list_filter = ('category', 'dosage_form', 'supplier')
    search_fields = ('name', 'barcode')
    readonly_fields = ('purchase_price', 'sale_price', 'total_stock', 'total_expired_stock', 'created_at', 'updated_at')
    fieldsets = (
        (None, {'fields': ('name', 'barcode', 'category', 'dosage_form', 'supplier', 'image')}),
        ('Stock & prix', {'fields': ('purchase_price', 'sale_price', 'total_stock', 'total_expired_stock', 'stock_threshold')}),
        ('Informations complémentaires', {'fields': ('notes', 'created_at', 'updated_at')}),
    )


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(ImportExportModelAdmin):
    list_display = ('id', 'supplier', 'order_date', 'receipt_date', 'status')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('supplier__name', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'order_date'


@admin.register(Lot)
class LotAdmin(ImportExportModelAdmin):
    list_display = (
        'product',
        'purchase_order',
        'quantity',
        'remaining_quantity',
        'expiration_date',
        'sale_price',
        'is_active',
        'is_expired',
    )
    list_filter = ('is_active', 'expiration_date', 'purchase_order__supplier')
    search_fields = ('product__name', 'product__barcode', 'batch_number')
    readonly_fields = ('is_expired', 'is_exhausted', 'created_at', 'updated_at')
    date_hierarchy = 'expiration_date'
    fieldsets = (
        (None, {'fields': ('purchase_order', 'product', 'batch_number')}),
        ('Quantités', {'fields': ('quantity', 'remaining_quantity')}),
        ('Prix & dates', {'fields': ('purchase_price', 'sale_price', 'expiration_date')}),
        ('Statut', {'fields': ('is_active', 'is_expired', 'is_exhausted', 'created_at', 'updated_at')}),
    )


@admin.register(StockMovement)
class StockMovementAdmin(ImportExportModelAdmin):
    list_display = ('lot', 'movement_type', 'quantity', 'movement_date', 'source')
    list_filter = ('movement_type', 'movement_date')
    search_fields = ('lot__product__name', 'source')
    readonly_fields = ('created_at', 'updated_at')
