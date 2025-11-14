"""
URLs pour l'API de vente.
"""

from django.urls import path

from . import api_views

app_name = 'sales_api'

urlpatterns = [
    path('products/search/', api_views.product_search, name='product_search'),
    path('products/<int:product_id>/stock/', api_views.product_stock_info, name='product_stock_info'),
    path('validate-item/', api_views.validate_sale_item, name='validate_sale_item'),
    path('customers/', api_views.customer_list, name='customer_list'),
    path('customers/<int:customer_id>/credit/', api_views.customer_credit_info, name='customer_credit_info'),
    path('create/', api_views.create_sale, name='create_sale'),
    path('<int:sale_id>/', api_views.sale_detail, name='sale_detail'),
    path('<int:sale_id>/update/', api_views.update_sale, name='update_sale'),
]

