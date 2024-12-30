# fortunaisk/migrations/0001_initial.py

# Standard Library
from decimal import Decimal

# Django
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def setup_periodic_tasks_func(apps, schema_editor):
    """
    Executes the function to set up global periodic tasks.
    """
    # Importing here to ensure the apps registry is ready
    # fortunaisk
    from fortunaisk.tasks import setup_periodic_tasks

    setup_periodic_tasks()


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        (
            "auth",
            "0012_alter_user_first_name_max_length",
        ),  # Ajustez en fonction de votre version de Django
        # Ajoutez d'autres dépendances si nécessaire
    ]

    operations = [
        # Create Lottery Model
        migrations.CreateModel(
            name="Lottery",
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
                (
                    "lottery_reference",
                    models.CharField(
                        max_length=20,
                        unique=True,
                        blank=True,
                        null=True,
                        db_index=True,
                        verbose_name="Lottery Reference",
                    ),
                ),
                (
                    "ticket_price",
                    models.DecimalField(
                        max_digits=20,
                        decimal_places=2,
                        verbose_name="Ticket Price (ISK)",
                        help_text="Price of a lottery ticket in ISK.",
                    ),
                ),
                (
                    "start_date",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="Start Date"
                    ),
                ),
                (
                    "end_date",
                    models.DateTimeField(db_index=True, verbose_name="End Date"),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="active",
                        db_index=True,
                        verbose_name="Lottery Status",
                    ),
                ),
                (
                    "winners_distribution",
                    models.JSONField(
                        default=list,
                        blank=True,
                        verbose_name="Winners Distribution",
                        help_text="List of percentage distributions for winners (sum must be 100).",
                    ),
                ),
                (
                    "max_tickets_per_user",
                    models.PositiveIntegerField(
                        null=True,
                        blank=True,
                        verbose_name="Max Tickets Per User",
                        help_text="Leave blank for unlimited.",
                    ),
                ),
                (
                    "total_pot",
                    models.DecimalField(
                        max_digits=25,
                        decimal_places=2,
                        default=Decimal("0"),
                        verbose_name="Total Pot (ISK)",
                        help_text="Total ISK pot from ticket purchases.",
                    ),
                ),
                (
                    "duration_value",
                    models.PositiveIntegerField(
                        default=24,
                        verbose_name="Duration Value",
                        help_text="Numeric part of the lottery duration.",
                    ),
                ),
                (
                    "duration_unit",
                    models.CharField(
                        max_length=10,
                        choices=[
                            ("hours", "Hours"),
                            ("days", "Days"),
                            ("months", "Months"),
                        ],
                        default="hours",
                        verbose_name="Duration Unit",
                        help_text="Unit of time for lottery duration.",
                    ),
                ),
                (
                    "winner_count",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Number of Winners"
                    ),
                ),
                (
                    "payment_receiver",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lotteries",
                        to="eveonline.evecorporationinfo",
                        verbose_name="Payment Receiver",
                        help_text="The corporation receiving the payments.",
                    ),
                ),
            ],
            options={
                "ordering": ["-start_date"],
                "permissions": [
                    ("user", "User permission"),
                    ("admin", "Administrator permission"),
                ],
            },
        ),
        # Create AutoLottery Model
        migrations.CreateModel(
            name="AutoLottery",
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
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Is Active"),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=100, unique=True, verbose_name="AutoLottery Name"
                    ),
                ),
                (
                    "frequency",
                    models.PositiveIntegerField(verbose_name="Frequency Value"),
                ),
                (
                    "frequency_unit",
                    models.CharField(
                        max_length=10,
                        choices=[
                            ("minutes", "Minutes"),
                            ("hours", "Hours"),
                            ("days", "Days"),
                            ("months", "Months"),
                        ],
                        default="days",
                        verbose_name="Frequency Unit",
                    ),
                ),
                (
                    "ticket_price",
                    models.DecimalField(
                        max_digits=20,
                        decimal_places=2,
                        verbose_name="Ticket Price (ISK)",
                    ),
                ),
                (
                    "duration_value",
                    models.PositiveIntegerField(
                        verbose_name="Lottery Duration Value",
                        help_text="Numeric part of the lottery duration.",
                    ),
                ),
                (
                    "duration_unit",
                    models.CharField(
                        max_length=10,
                        choices=[
                            ("hours", "Hours"),
                            ("days", "Days"),
                            ("months", "Months"),
                        ],
                        default="hours",
                        verbose_name="Lottery Duration Unit",
                    ),
                ),
                (
                    "winner_count",
                    models.PositiveIntegerField(
                        default=1, verbose_name="Number of Winners"
                    ),
                ),
                (
                    "winners_distribution",
                    models.JSONField(
                        default=list, blank=True, verbose_name="Winners Distribution"
                    ),
                ),
                (
                    "max_tickets_per_user",
                    models.PositiveIntegerField(
                        null=True,
                        blank=True,
                        verbose_name="Max Tickets Per User",
                        help_text="Leave blank for unlimited tickets.",
                    ),
                ),
                (
                    "payment_receiver",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        verbose_name="Payment Receiver",
                        help_text="The corporation receiving the payments.",
                        to="eveonline.evecorporationinfo",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "permissions": [],
            },
        ),
        # Create TicketPurchase Model
        migrations.CreateModel(
            name="TicketPurchase",
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
                (
                    "amount",
                    models.DecimalField(
                        max_digits=25,
                        decimal_places=2,
                        default=Decimal("0"),
                        verbose_name="Ticket Amount",
                        help_text="Amount of ISK paid for this ticket.",
                    ),
                ),
                (
                    "purchase_date",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Purchase Date"
                    ),
                ),
                (
                    "payment_id",
                    models.CharField(
                        max_length=255,
                        null=True,
                        blank=True,
                        verbose_name="Payment ID",
                        unique=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("processed", "Processed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                        verbose_name="Ticket Status",
                    ),
                ),
                (
                    "lottery",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ticket_purchases",
                        to="fortunaisk.lottery",
                        verbose_name="Lottery",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ticket_purchases",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Django User",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ticket_purchases",
                        to="eveonline.evecharacter",
                        null=True,
                        blank=True,
                        verbose_name="Eve Character",
                        help_text="Eve character that made the payment (if identifiable).",
                    ),
                ),
            ],
            # Supprimer ou laisser vide les options pour éviter les Altérations ultérieures
            options={
                # "ordering": ["-purchase_date"],  # Commenté ou supprimé
            },
        ),
        # Create Winner Model
        migrations.CreateModel(
            name="Winner",
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
                (
                    "prize_amount",
                    models.DecimalField(
                        max_digits=25,
                        decimal_places=2,
                        default=0,
                        verbose_name="Prize Amount",
                        help_text="ISK amount that the winner receives.",
                    ),
                ),
                (
                    "won_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Winning Date"
                    ),
                ),
                (
                    "distributed",
                    models.BooleanField(
                        default=False,
                        verbose_name="Prize Distributed",
                        help_text="Indicates whether the prize has been distributed to the winner.",
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="winners",
                        to="fortunaisk.ticketpurchase",
                        verbose_name="Ticket Purchase",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="winners",
                        to="eveonline.evecharacter",
                        null=True,
                        blank=True,
                        verbose_name="Winning Eve Character",
                    ),
                ),
            ],
            options={
                # "ordering": ["-won_at"],  # Commenté ou supprimé
            },
        ),
        # Create TicketAnomaly Model
        migrations.CreateModel(
            name="TicketAnomaly",
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
                (
                    "reason",
                    models.TextField(verbose_name="Anomaly Reason"),
                ),
                (
                    "payment_date",
                    models.DateTimeField(verbose_name="Payment Date"),
                ),
                (
                    "amount",
                    models.DecimalField(
                        max_digits=25,
                        decimal_places=2,
                        default=Decimal("0"),
                        verbose_name="Anomaly Amount",
                    ),
                ),
                (
                    "payment_id",
                    models.CharField(
                        max_length=255,
                        verbose_name="Payment ID",
                    ),
                ),
                (
                    "recorded_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Recorded At"),
                ),
                (
                    "lottery",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="anomalies",
                        to="fortunaisk.lottery",
                        verbose_name="Lottery",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        verbose_name="Eve Character",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.SET_NULL,
                        null=True,
                        blank=True,
                        verbose_name="Django User",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            # Supprimer ou laisser vide les options pour éviter les Altérations ultérieures
            options={
                # "ordering": ["-recorded_at"],  # Commenté ou supprimé
            },
        ),
        # Create WebhookConfiguration Model
        migrations.CreateModel(
            name="WebhookConfiguration",
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
                (
                    "webhook_url",
                    models.URLField(
                        verbose_name="Discord Webhook URL",
                        help_text="The URL for sending Discord notifications",
                        blank=True,
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Webhook Configuration",
                "verbose_name_plural": "Webhook Configuration",
            },
        ),
        # Create AuditLog Model
        migrations.CreateModel(
            name="AuditLog",
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
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("create", "Create"),
                            ("update", "Update"),
                            ("delete", "Delete"),
                        ],
                        help_text="The type of action performed.",
                        max_length=10,
                        verbose_name="Action Type",
                    ),
                ),
                (
                    "timestamp",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="The date and time when the action was performed.",
                        verbose_name="Timestamp",
                    ),
                ),
                (
                    "model",
                    models.CharField(
                        help_text="The model on which the action was performed.",
                        max_length=100,
                        verbose_name="Model",
                    ),
                ),
                (
                    "object_id",
                    models.PositiveIntegerField(
                        help_text="The ID of the object on which the action was performed.",
                        verbose_name="Object ID",
                    ),
                ),
                (
                    "changes",
                    models.JSONField(
                        blank=True,
                        help_text="A JSON object detailing the changes made.",
                        null=True,
                        verbose_name="Changes",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        help_text="The user who performed the action.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="User",
                    ),
                ),
            ],
            options={
                "verbose_name": "Audit Log",
                "verbose_name_plural": "Audit Logs",
                "ordering": ["-timestamp"],
            },
        ),
        # Create ProcessedPayment Model
        migrations.CreateModel(
            name="ProcessedPayment",
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
                (
                    "payment_id",
                    models.CharField(
                        help_text="Unique identifier for processed payments.",
                        max_length=255,
                        unique=True,
                        verbose_name="Payment ID",
                    ),
                ),
                (
                    "processed_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="Timestamp when the payment was processed.",
                        verbose_name="Processed At",
                    ),
                ),
            ],
            options={
                # "verbose_name": "Processed Payment",
                # "verbose_name_plural": "Processed Payments",
                # "ordering": ["-processed_at"],
                # Commenté ou supprimé pour correspondre à la migration `AlterModelOptions`
            },
        ),
        # Setup Periodic Tasks
        migrations.RunPython(
            setup_periodic_tasks_func,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

    # Généré par Django 4.2.17 sur 2024-12-30 00:15

# Generated by Django 4.2.17 on 2024-12-30 00:34

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('fortunaisk', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='processedpayment',
            options={},
        ),
        migrations.AlterModelOptions(
            name='ticketanomaly',
            options={},
        ),
        migrations.AlterModelOptions(
            name='ticketpurchase',
            options={},
        ),
        migrations.AlterModelOptions(
            name='winner',
            options={},
        ),
    ]
