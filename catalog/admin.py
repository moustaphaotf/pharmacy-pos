from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import Category, DosageForm, Product, StockMovement, Supplier


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
        ('Stock & prix', {'fields': ('purchase_price', 'sale_price', 'stock_quantity', 'stock_threshold', 'expiration_date')}),
        ('Informations complémentaires', {'fields': ('notes', 'created_at', 'updated_at')}),
    )


@admin.register(StockMovement)
class StockMovementAdmin(ImportExportModelAdmin):
    list_display = ('product', 'movement_type', 'quantity', 'movement_date', 'source')
    list_filter = ('movement_type', 'movement_date')
    search_fields = ('product__name', 'source')
