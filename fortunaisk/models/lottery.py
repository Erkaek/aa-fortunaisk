# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string
from datetime import timedelta
from decimal import Decimal

# Django
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo

# fortunaisk
from fortunaisk.models.ticket import TicketPurchase

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
        default=0,
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
        ordering = ["-start_date"]
        permissions = [
            ("user", "User permission"),
            ("admin", "Administrator permission"),
        ]

    def __str__(self) -> str:
        return f"Lottery {self.lottery_reference} [{self.status}]"

    @staticmethod
    def generate_unique_reference() -> str:
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def clean(self):
        """Validate that winners_distribution sums to 100% and matches winner_count."""
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
        if self._state.adding:
            pass  # Any post-creation logic

    def get_duration_timedelta(self) -> timedelta:
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(days=30 * self.duration_value)
        return timedelta(hours=self.duration_value)

    def update_total_pot(self):
        """Recalculate the pot based on ticket_price * number of purchased tickets."""
        ticket_count = self.ticket_purchases.count()
        self.total_pot = self.ticket_price * Decimal(ticket_count)
        self.save(update_fields=["total_pot"])

    def complete_lottery(self):
        """
        Trigger the completion of the lottery:
        - Update the pot
        - Launch the Celery task to finalize the lottery
        """
        if self.status != "active":
            logger.info(
                f"Lottery {self.lottery_reference} is not active. Current status: {self.status}"
            )
            return

        self.update_total_pot()

        if self.total_pot <= Decimal("0"):
            logger.error(
                f"Lottery {self.lottery_reference} pot is 0. Marking completed."
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
        Randomly select winner_count tickets (or fewer if not enough).
        Create a Winner for each selected ticket.
        """
        # fortunaisk
        from fortunaisk.models.ticket import Winner

        tickets = TicketPurchase.objects.filter(lottery=self)
        ticket_ids = list(tickets.values_list("id", flat=True))
        if not ticket_ids:
            logger.info(f"No tickets in lottery {self.lottery_reference}.")
            return []

        if len(ticket_ids) < self.winner_count:
            logger.warning(f"Not enough tickets to select {self.winner_count} winners.")
            selected_ids = ticket_ids
        else:
            # Standard Library
            selected_ids = random.sample(ticket_ids, self.winner_count)

        winners = []
        for idx, ticket_id in enumerate(selected_ids):
            try:
                ticket = tickets.get(id=ticket_id)
                percentage_decimal = Decimal(str(self.winners_distribution[idx]))
                prize_amount = (self.total_pot * percentage_decimal) / Decimal("100")
                prize_amount = prize_amount.quantize(Decimal("0.01"))
                winner = Winner.objects.create(
                    character=ticket.character,
                    ticket=ticket,
                    prize_amount=prize_amount,
                )
                winners.append(winner)
            except EveCharacter.DoesNotExist:
                logger.warning(
                    f"The EveCharacter for ticket ID {ticket_id} does not exist. Skipping."
                )
                continue
            except Exception as e:
                logger.error(
                    f"Error creating Winner for ticket ID {ticket_id}: {e}",
                    exc_info=True,
                )
                continue

        return winners

    @property
    def winners(self):
        # fortunaisk
        from fortunaisk.models.ticket import Winner

        return Winner.objects.filter(ticket__lottery=self)
