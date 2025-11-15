"""
URLs pour les factures.
"""

from django.urls import path

from . import views

app_name = 'invoices'

urlpatterns = [
    path('<int:invoice_id>/preview/', views.invoice_preview, name='invoice_preview'),
    path('<int:invoice_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
]

