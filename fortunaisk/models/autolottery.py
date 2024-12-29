# fortunaisk/models/autolottery.py

# Standard Library
import logging
from datetime import timedelta  # Already used in get_duration_timedelta

# Django
from django.apps import apps  # For using apps.get_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone  # For timezone.now
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

logger = logging.getLogger(__name__)


class AutoLottery(models.Model):
    FREQUENCY_UNITS = [
        ("minutes", "Minutes"),
        ("hours", "Hours"),
        ("days", "Days"),
        ("months", "Months"),
    ]
    DURATION_UNITS = [
        ("hours", "Hours"),
        ("days", "Days"),
        ("months", "Months"),
    ]

    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    name = models.CharField(
        max_length=100, unique=True, verbose_name="AutoLottery Name"
    )
    frequency = models.PositiveIntegerField(verbose_name="Frequency Value")
    frequency_unit = models.CharField(
        max_length=10,
        choices=FREQUENCY_UNITS,
        default="days",
        verbose_name="Frequency Unit",
    )
    ticket_price = models.DecimalField(
        max_digits=20, decimal_places=2, verbose_name="Ticket Price (ISK)"
    )
    duration_value = models.PositiveIntegerField(
        verbose_name="Lottery Duration Value",
        help_text="Numeric part of the lottery duration.",
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNITS,
        default="hours",
        verbose_name="Lottery Duration Unit",
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Number of Winners"
    )
    winners_distribution = models.JSONField(
        default=list, blank=True, verbose_name="Winners Distribution"
    )
    max_tickets_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Max Tickets Per User",
        help_text="Leave blank for unlimited tickets.",
    )
    payment_receiver = models.ForeignKey(
        EveCorporationInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Payment Receiver",
        help_text="The corporation receiving the payments.",
    )

    class Meta:
        ordering = ["name"]
        permissions = []

    def __str__(self):
        return f"{self.name} (Active={self.is_active})"

    def clean(self):
        """
        Validates that winners_distribution sums to 100% and matches winner_count.
        """
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

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self):
        # Uses timedelta imported at the top
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(days=30 * self.duration_value)
        return timedelta(hours=self.duration_value)

    def create_lottery(self):
        """
        Creates a new Lottery based on this AutoLottery.
        """
        Lottery = apps.get_model("fortunaisk", "Lottery")
        new_lottery = Lottery.objects.create(
            ticket_price=self.ticket_price,
            start_date=timezone.now(),
            end_date=timezone.now() + self.get_duration_timedelta(),
            payment_receiver=self.payment_receiver,
            winner_count=self.winner_count,
            winners_distribution=self.winners_distribution,
            max_tickets_per_user=self.max_tickets_per_user,
            lottery_reference=Lottery.generate_unique_reference(),
            duration_value=self.duration_value,
            duration_unit=self.duration_unit,
        )
        logger.info(
            f"AutoLottery '{self.name}' created Lottery '{new_lottery.lottery_reference}'"
        )
        return new_lottery
