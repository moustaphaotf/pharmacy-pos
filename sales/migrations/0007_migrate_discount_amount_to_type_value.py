# Generated migration to migrate existing discount_amount to discount_type and discount_value

from django.db import migrations
from decimal import Decimal


def migrate_discount_amount_to_type_value(apps, schema_editor):
    """
    Migre les discount_amount existants vers discount_type='amount' et discount_value.
    """
    Sale = apps.get_model('sales', 'Sale')
    
    for sale in Sale.objects.all():
        if sale.discount_amount and sale.discount_amount > 0:
            # Si discount_value est 0, on migre depuis discount_amount
            if sale.discount_value == 0:
                sale.discount_type = 'amount'
                sale.discount_value = sale.discount_amount
                sale.save(update_fields=['discount_type', 'discount_value'])


def reverse_migrate(apps, schema_editor):
    """
    Migration inverse : remet discount_amount depuis discount_value si type='amount'.
    """
    Sale = apps.get_model('sales', 'Sale')
    
    for sale in Sale.objects.all():
        if sale.discount_type == 'amount' and sale.discount_value > 0:
            sale.discount_amount = sale.discount_value
            sale.save(update_fields=['discount_amount'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0006_add_discount_type_and_value'),
    ]

    operations = [
        migrations.RunPython(migrate_discount_amount_to_type_value, reverse_migrate),
    ]

