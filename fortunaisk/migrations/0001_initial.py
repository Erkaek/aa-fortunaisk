# fortunaisk/migrations/0001_initial.py

# Standard Library
from decimal import Decimal

# Django
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        (
            "auth",
            "0012_alter_user_first_name_max_length",
        ),  # Ajustez en fonction de votre version de Django
        # Ajoutez d'autres dépendances si nécessaire
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
                ("start_date", models.DateTimeField(verbose_name="Start Date")),
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
                        default=0,
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
                    ("view_lotteryhistory", "Can view lottery history"),
                    ("terminate_lottery", "Can terminate a lottery"),
                    ("admin_dashboard", "Can access the admin dashboard"),
                ],
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
                        to="auth.user",
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
                    models.OneToOneField(
                        on_delete=models.CASCADE,
                        related_name="winner",
                        to="fortunaisk.ticketpurchase",
                        verbose_name="Ticket Purchase",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=models.SET_NULL,
                        related_name="winners",
                        to="eveonline.evecharacter",
                        null=True,
                        blank=True,
                        verbose_name="Winning Eve Character",
                    ),
                ),
            ],
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
                        max_digits=25,
                        decimal_places=2,
                        default=Decimal("0"),
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
                    "lottery",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="anomalies",
                        to="fortunaisk.lottery",
                        verbose_name="Lottery",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        on_delete=models.SET_NULL,
                        null=True,
                        blank=True,
                        verbose_name="Eve Character",
                        to="eveonline.evecharacter",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.SET_NULL,
                        null=True,
                        blank=True,
                        verbose_name="Django User",
                        to="auth.user",
                    ),
                ),
            ],
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
    ]
