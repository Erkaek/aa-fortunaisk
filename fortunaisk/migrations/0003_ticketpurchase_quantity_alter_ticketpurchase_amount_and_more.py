# Generated by Django 4.2.20 on 2025-05-08 18:49

# Standard Library
from decimal import Decimal

# Django
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fortunaisk", "0002_general_alter_auditlog_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketpurchase",
            name="quantity",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Number of tickets purchased in this transaction.",
                verbose_name="Ticket Quantity",
            ),
        ),
        migrations.AlterField(
            model_name="ticketpurchase",
            name="amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text="Total cost of the lottery tickets purchased in ISK.",
                max_digits=25,
                verbose_name="Total Ticket Amount",
            ),
        ),
        migrations.AlterField(
            model_name="ticketpurchase",
            name="payment_id",
            field=models.CharField(
                blank=True, max_length=255, null=True, verbose_name="Payment ID"
            ),
        ),
        migrations.DeleteModel(
            name="AuditLog",
        ),
    ]
