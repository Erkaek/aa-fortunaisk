# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

# Django
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

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
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Ticket Price (ISK)",
        help_text="Price of a lottery ticket in ISK.",
    )
    start_date = models.DateTimeField(
        verbose_name="Start Date",
        default=timezone.now,
    )
    end_date = models.DateTimeField(db_index=True, verbose_name="End Date")
    payment_receiver = models.ForeignKey(
        EveCorporationInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lotteries",
        verbose_name="Payment Receiver",
        help_text="The corporation receiving the payments.",
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
    winners_distribution = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Winners Distribution",
        help_text="List of percentage distributions for winners (sum must be 100).",
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
        help_text="Total ISK pot from ticket purchases.",
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

    def __str__(self) -> str:
        return f"Lottery {self.lottery_reference} [{self.status}]"

    @staticmethod
    def generate_unique_reference() -> str:
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def clean(self):
        """Validate that winners_distribution sums to 100 and matches winner_count."""
        if self.winners_distribution:
            if len(self.winners_distribution) != self.winner_count:
                raise ValidationError(
                    {
                        "winners_distribution": _(
                            "Distribution must match the number of winners."
                        )
                    }
                )
            total = sum(self.winners_distribution)
            if abs(total - 100.0) > 0.001:
                raise ValidationError(
                    {
                        "winners_distribution": _(
                            "The sum of percentages must equal 100."
                        )
                    }
                )

    def save(self, *args, **kwargs) -> None:
        self.clean()
        if not self.lottery_reference:
            self.lottery_reference = self.generate_unique_reference()
        self.end_date = self.start_date + self.get_duration_timedelta()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self) -> timedelta:
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(days=30 * self.duration_value)
        return timedelta(hours=self.duration_value)

    def update_total_pot(self):
        """Recalculate the pot based on the sum of ticket purchase amounts."""
        self.total_pot = self.ticket_purchases.aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        self.save(update_fields=["total_pot"])

    def complete_lottery(self):
        """
        Trigger the completion of the lottery:
        - Update the pot.
        - Launch the Celery task to finalize the lottery.
        """
        if self.status != "active":
            logger.info(
                f"Lottery {self.lottery_reference} is not active. Current status: {self.status}"
            )
            return

        self.update_total_pot()

        if self.total_pot <= Decimal("0"):
            logger.error(
                f"Lottery {self.lottery_reference} pot is 0. Marking as completed."
            )
            self.status = "completed"
            self.save(update_fields=["status"])
            return

        # fortunaisk
        from fortunaisk.tasks import finalize_lottery

        finalize_lottery.delay(self.id)
        logger.info(
            f"Task finalize_lottery initiated for lottery {self.lottery_reference}."
        )

    def select_winners(self):
        """
        Select winners using weighted random selection based on the 'quantity' field.
        Each TicketPurchase record represents a number of tickets.
        The prize for each winner is calculated based on the winners_distribution.
        """
        # Re-read the pot total
        total_pot = self.ticket_purchases.aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        logger.debug(
            f"Total pot for lottery {self.lottery_reference} is {total_pot} ISK."
        )

        if total_pot <= Decimal("0"):
            logger.error(
                f"Total pot is 0 for lottery {self.lottery_reference}. Cannot select winners."
            )
            return []

        # fortunaisk
        from fortunaisk.models.ticket import TicketPurchase, Winner

        purchases = TicketPurchase.objects.filter(lottery=self, status="processed")
        if not purchases.exists():
            logger.info(f"No tickets in lottery {self.lottery_reference}.")
            return []

        entries = list(purchases)
        weights = [entry.quantity for entry in entries]
        total_quantity = sum(weights)
        logger.debug(
            f"Total ticket quantity for lottery {self.lottery_reference} is {total_quantity}."
        )

        if total_quantity == 0:
            logger.warning(
                f"Total ticket quantity is 0 for lottery {self.lottery_reference}."
            )
            return []

        # Utiliser une distribution par défaut si nécessaire
        if (
            not self.winners_distribution
            or len(self.winners_distribution) != self.winner_count
        ):
            distribution = [Decimal("100")] * self.winner_count
        else:
            distribution = [Decimal(str(p)) for p in self.winners_distribution]

        # Sélection pondérée
        selected_entries = random.choices(entries, weights=weights, k=self.winner_count)

        winners = []
        for idx, purchase in enumerate(selected_entries):
            try:
                percentage = distribution[idx]
                prize_amount = (total_pot * percentage / Decimal("100")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                logger.debug(
                    f"Lottery {self.lottery_reference}: For TicketPurchase ID {purchase.id}, "
                    f"using distribution {percentage}% => prize amount {prize_amount} ISK."
                )
                winner = Winner.objects.create(
                    character=purchase.character,
                    ticket=purchase,
                    prize_amount=prize_amount,
                )
                winners.append(winner)
            except Exception as e:
                logger.error(
                    f"Error creating Winner for TicketPurchase ID {purchase.id}: {e}",
                    exc_info=True,
                )
                continue

        return winners

    @property
    def winners(self):
        # fortunaisk
        from fortunaisk.models.ticket import Winner

        return Winner.objects.filter(ticket__lottery=self)

    @property
    def total_tickets(self):
        """Return the total number of tickets purchased for this lottery."""
        agg = self.ticket_purchases.aggregate(total=models.Sum("quantity"))
        return agg["total"] or 0
