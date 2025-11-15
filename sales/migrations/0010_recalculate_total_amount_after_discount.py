# Generated migration to recalculate total_amount after discount for existing sales

from decimal import Decimal
from django.db import migrations
from django.db.models import Sum


def recalculate_total_amount_after_discount(apps, schema_editor):
    """
    Recalcule le total_amount pour toutes les ventes existantes en tenant compte de la remise.
    Le total_amount doit être (items_total - discount_amount) + tax_amount.
    """
    Sale = apps.get_model('sales', 'Sale')
    SaleItem = apps.get_model('sales', 'SaleItem')
    
    for sale in Sale.objects.all():
        # Calculer le total des items
        items_total = Decimal('0.00')
        for item in SaleItem.objects.filter(sale=sale):
            items_total += item.line_total
        
        # Calculer le montant de la remise
        discount_amount = Decimal('0.00')
        if sale.discount_type == 'percentage':
            discount_amount = items_total * (sale.discount_value / Decimal('100.00'))
        else:  # amount
            discount_amount = sale.discount_value
        
        # Calculer le subtotal après remise
        subtotal_after_discount = items_total - discount_amount
        
        # Calculer le total_amount (subtotal après remise + taxe)
        total_amount = subtotal_after_discount + sale.tax_amount
        
        # Recalculer le statut basé sur le nouveau total_amount
        if sale.amount_paid >= total_amount:
            new_status = 'paid'
        elif sale.amount_paid > 0:
            new_status = 'partial'
        else:
            new_status = 'pending'
        
        # Mettre à jour la vente
        sale.subtotal = subtotal_after_discount
        sale.total_amount = total_amount
        sale.balance_due = total_amount - sale.amount_paid
        sale.status = new_status
        sale.save(update_fields=['subtotal', 'total_amount', 'balance_due', 'status', 'updated_at'])


def reverse_migrate(apps, schema_editor):
    """
    Migration inverse : ne fait rien, on garde les nouveaux calculs.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0009_alter_sale_status'),
    ]

    operations = [
        migrations.RunPython(recalculate_total_amount_after_discount, reverse_migrate),
    ]

