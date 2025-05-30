# fortunaisk/migrations/0001_initial.py
"""
Initial migration creating all core models for the FortunaISK application.

This migration creates the following models:
- Lottery: For managing lottery events
- ProcessedPayment: For tracking payment processing
- TicketPurchase: For recording ticket purchases
- WebhookConfiguration: For Discord integration
- Winner: For tracking lottery winners
- TicketAnomaly: For tracking payment anomalies
- AutoLottery: For automatic lottery creation
- AuditLog: For tracking system changes
"""

# Standard Library
from decimal import Decimal

# Django
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("eveonline", "0017_alliance_and_corp_names_are_not_unique"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
                    "ticket_price",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Price of a lottery ticket in ISK.",
                        max_digits=20,
                        verbose_name="Ticket Price (ISK)",
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
                    "lottery_reference",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=20,
                        null=True,
                        unique=True,
                        verbose_name="Lottery Reference",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        db_index=True,
                        default="active",
                        max_length=20,
                        verbose_name="Lottery Status",
                    ),
                ),
                (
                    "winners_distribution",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="List of percentage distributions for winners (sum must be 100).",
                        verbose_name="Winners Distribution",
                    ),
                ),
                (
                    "max_tickets_per_user",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Leave blank for unlimited.",
                        null=True,
                        verbose_name="Max Tickets Per User",
                    ),
                ),
                (
                    "total_pot",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Total ISK pot from ticket purchases.",
                        max_digits=25,
                        verbose_name="Total Pot (ISK)",
                    ),
                ),
                (
                    "duration_value",
                    models.PositiveIntegerField(
                        default=24,
                        help_text="Numeric part of the lottery duration.",
                        verbose_name="Duration Value",
                    ),
                ),
                (
                    "duration_unit",
                    models.CharField(
                        choices=[
                            ("hours", "Hours"),
                            ("days", "Days"),
                            ("months", "Months"),
                        ],
                        default="hours",
                        help_text="Unit of time for lottery duration.",
                        max_length=10,
                        verbose_name="Duration Unit",
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
                        help_text="The corporation receiving the payments.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="lotteries",
                        to="eveonline.evecorporationinfo",
                        verbose_name="Payment Receiver",
                    ),
                ),
            ],
            options={
                "ordering": ["-start_date"],
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
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
                "verbose_name": "Processed Payment",
                "verbose_name_plural": "Processed Payments",
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
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
                        decimal_places=2,
                        default=Decimal("0"),
                        help_text="Amount of ISK paid for this ticket.",
                        max_digits=25,
                        verbose_name="Ticket Amount",
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
                        blank=True,
                        max_length=255,
                        null=True,
                        unique=True,
                        verbose_name="Payment ID",
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
                    "character",
                    models.ForeignKey(
                        blank=True,
                        help_text="Eve character that made the payment (if identifiable).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ticket_purchases",
                        to="eveonline.evecharacter",
                        verbose_name="Eve Character",
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
            ],
            options={
                "verbose_name": "Ticket Purchase",
                "verbose_name_plural": "Ticket Purchases",
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
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
                        blank=True,
                        help_text="The URL for sending Discord notifications",
                        null=True,
                        verbose_name="Discord Webhook URL",
                    ),
                ),
            ],
            options={
                "verbose_name": "Webhook Configuration",
                "verbose_name_plural": "Webhook Configuration",
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
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
                        decimal_places=2,
                        default=Decimal("0"),
                        help_text="ISK amount that the winner receives.",
                        max_digits=25,
                        verbose_name="Prize Amount",
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
                        help_text="Indicates whether the prize has been distributed to the winner.",
                        verbose_name="Prize Distributed",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="winners",
                        to="eveonline.evecharacter",
                        verbose_name="Winning Eve Character",
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
            ],
            options={
                "verbose_name": "Winner",
                "verbose_name_plural": "Winners",
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
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
                ("reason", models.TextField(verbose_name="Anomaly Reason")),
                ("payment_date", models.DateTimeField(verbose_name="Payment Date")),
                (
                    "amount",
                    models.DecimalField(
                        decimal_places=2,
                        default=Decimal("0"),
                        max_digits=25,
                        verbose_name="Anomaly Amount",
                    ),
                ),
                (
                    "payment_id",
                    models.CharField(max_length=255, verbose_name="Payment ID"),
                ),
                (
                    "recorded_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Recorded At"),
                ),
                (
                    "character",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="eveonline.evecharacter",
                        verbose_name="Eve Character",
                    ),
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
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Django User",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ticket Anomaly",
                "verbose_name_plural": "Ticket Anomalies",
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
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
                        choices=[
                            ("minutes", "Minutes"),
                            ("hours", "Hours"),
                            ("days", "Days"),
                            ("months", "Months"),
                        ],
                        default="days",
                        max_length=10,
                        verbose_name="Frequency Unit",
                    ),
                ),
                (
                    "ticket_price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=20,
                        verbose_name="Ticket Price (ISK)",
                    ),
                ),
                (
                    "duration_value",
                    models.PositiveIntegerField(
                        help_text="Numeric part of the lottery duration.",
                        verbose_name="Lottery Duration Value",
                    ),
                ),
                (
                    "duration_unit",
                    models.CharField(
                        choices=[
                            ("hours", "Hours"),
                            ("days", "Days"),
                            ("months", "Months"),
                        ],
                        default="hours",
                        max_length=10,
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
                        blank=True, default=list, verbose_name="Winners Distribution"
                    ),
                ),
                (
                    "max_tickets_per_user",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Leave blank for unlimited tickets.",
                        null=True,
                        verbose_name="Max Tickets Per User",
                    ),
                ),
                (
                    "payment_receiver",
                    models.ForeignKey(
                        blank=True,
                        help_text="The corporation receiving the payments.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="eveonline.evecorporationinfo",
                        verbose_name="Payment Receiver",
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
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
                "permissions": [
                    ("user", "can access this app"),
                    ("admin", "can admin this app"),
                ],
                "default_permissions": (),
            },
        ),
    ]
