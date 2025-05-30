# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

# Django
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

logger = logging.getLogger(__name__)


class Lottery(models.Model):
    DURATION_UNITS = [
        ("hours", "Hours"),
        ("days", "Days"),
        ("months", "Months"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Ticket Price (ISK)",
        help_text="Price of a lottery ticket in ISK.",
    )
    start_date = models.DateTimeField(verbose_name="Start Date", default=timezone.now)
    end_date = models.DateTimeField(verbose_name="End Date", db_index=True)
    payment_receiver = models.ForeignKey(
        EveCorporationInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lotteries",
        verbose_name="Payment Receiver",
    )
    lottery_reference = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Lottery Reference",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
        verbose_name="Lottery Status",
    )
    max_tickets_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Max Tickets Per User",
        help_text="Leave blank for unlimited.",
    )
    total_pot = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total Pot (ISK)",
        help_text="Total ISK pot from ticket purchases after tax.",
    )
    tax = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Tax (%)",
        help_text="Percentage of tax applied to the gross pot before distribution.",
    )
    tax_amount = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Tax Amount (ISK)",
        help_text="Amount of tax (in ISK) computed from the gross pot.",
    )
    duration_value = models.PositiveIntegerField(
        default=24,
        verbose_name="Duration Value",
        help_text="Numeric part of the lottery duration.",
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNITS,
        default="hours",
        verbose_name="Duration Unit",
        help_text="Unit of time for lottery duration.",
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Number of Winners"
    )

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"Lottery {self.lottery_reference} [{self.status}]"

    @staticmethod
    def generate_unique_reference():
        """Generates a unique reference."""
        while True:
            ref = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=ref).exists():
                return ref

    def save(self, *args, **kwargs):
        """Before saving, generates the reference and updates end_date."""
        self.clean()
        if not self.lottery_reference:
            self.lottery_reference = self.generate_unique_reference()
        self.end_date = self.start_date + self.get_duration_timedelta()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self):
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        if self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        if self.duration_unit == "months":
            return timedelta(days=30 * self.duration_value)
        return timedelta(hours=self.duration_value)

    def update_total_pot(self):
        """Recalculates tax_amount and total_pot."""
        # fortunaisk
        from fortunaisk.models.ticket import TicketPurchase

        gross = TicketPurchase.objects.filter(lottery=self).aggregate(
            total=Coalesce(Sum("amount"), Decimal("0.00"))
        )["total"]
        tax_amt = (gross * self.tax / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        net = (gross - tax_amt).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        self.tax_amount = tax_amt
        self.total_pot = net
        self.save(update_fields=["tax_amount", "total_pot"])

    def complete_lottery(self):
        """Starts finalization if active."""
        if self.status != "active":
            logger.info(
                f"Lottery {self.lottery_reference} not active (status={self.status})."
            )
            return

        self.update_total_pot()
        if self.total_pot <= 0:
            logger.warning(f"Lottery {self.lottery_reference} pot zero → completed.")
            self.status = "completed"
            self.save(update_fields=["status"])
            return

        # fortunaisk
        from fortunaisk.tasks import finalize_lottery

        finalize_lottery.delay(self.id)
        logger.info(f"Scheduled finalize_lottery for {self.lottery_reference}.")

    def select_winners(self):
        """Selects `winner_count` TicketPurchase randomly, weighted by `quantity`."""
        # fortunaisk
        from fortunaisk.models.ticket import TicketPurchase

        purchases = list(
            TicketPurchase.objects.filter(lottery=self, status="processed")
        )
        if not purchases:
            logger.info(f"No tickets for {self.lottery_reference}.")
            return []

        weights = [p.quantity for p in purchases]
        return random.choices(purchases, weights=weights, k=self.winner_count)

    @property
    def winners(self):
        """All linked Winners."""
        # fortunaisk
        from fortunaisk.models.ticket import Winner

        return Winner.objects.filter(ticket__lottery=self)

    @property
    def total_tickets(self):
        """Sum of sold `quantity`."""
        return self.ticket_purchases.aggregate(total=Coalesce(Sum("quantity"), 0))[
            "total"
        ]

    @property
    def winners_distribution(self):
        """
        List of percentages as stored in the database
        in fortunaisk_winner_distribution.
        """
        # fortunaisk
        from fortunaisk.models.winner_distribution import WinnerDistribution

        return [
            wd.winner_prize_distribution
            for wd in WinnerDistribution.objects.filter(
                lottery_reference=self.lottery_reference
            ).order_by("winner_rank")
        ]
