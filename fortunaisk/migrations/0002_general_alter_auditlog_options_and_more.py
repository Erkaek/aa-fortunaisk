# fortunaisk/migrations/0002_general_alter_auditlog_options_and_more.py
"""
Migration to configure application-wide permissions and model defaults.

This migration:
1. Creates a General model with app-level permissions:
- can_access_app: Basic access to the application
- can_admin_app: Administrative privileges
2. Disables default Django permissions for all models to simplify access control
"""

# Django
from django.db import migrations, models


class Migration(migrations.Migration):
    """Sets up permission structure and model configurations."""

    dependencies = [
        ("fortunaisk", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="General",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "permissions": (
                    ("can_access_app", "Can access this app"),
                    ("can_admin_app", "Can admin this app"),
                ),
                "managed": False,
                "default_permissions": (),
            },
        ),
        migrations.AlterModelOptions(
            name="auditlog",
            options={"default_permissions": ()},
        ),
        migrations.AlterModelOptions(
            name="autolottery",
            options={"default_permissions": ()},
        ),
        migrations.AlterModelOptions(
            name="lottery",
            options={"default_permissions": ()},
        ),
        migrations.AlterModelOptions(
            name="processedpayment",
            options={"default_permissions": ()},
        ),
        migrations.AlterModelOptions(
            name="ticketanomaly",
            options={"default_permissions": ()},
        ),
        migrations.AlterModelOptions(
            name="ticketpurchase",
            options={"default_permissions": ()},
        ),
        migrations.AlterModelOptions(
            name="webhookconfiguration",
            options={"default_permissions": ()},
        ),
        migrations.AlterModelOptions(
            name="winner",
            options={"default_permissions": ()},
        ),
    ]
