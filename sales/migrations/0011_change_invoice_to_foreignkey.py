# Generated migration to change Invoice.sale from OneToOneField to ForeignKey

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0010_recalculate_total_amount_after_discount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='sale',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='invoices',
                to='sales.sale',
                verbose_name='Vente',
            ),
        ),
    ]

