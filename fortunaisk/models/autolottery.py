# fortunaisk/models/autolottery.py

# Standard Library
import logging
from datetime import timedelta
from decimal import Decimal

# Django
from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
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
        max_digits=20,
        decimal_places=2,
        verbose_name="Ticket Price (ISK)",
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
        default=list,
        blank=True,
        verbose_name="Winners Distribution",
        help_text="List of percentage distributions for winners (sum must be 100).",
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
    tax = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Tax (%)",
        help_text="Percentage of tax applied to the total pot before distribution.",
    )
    tax_amount = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Tax Amount (ISK)",
        help_text="Amount of tax (in ISK) computed from the gross pot.",
    )

    class Meta:
        default_permissions = ()

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
            total = sum(self.winners_distribution or [])
            if abs(Decimal(total) - Decimal("100")) > Decimal("0.001"):
                raise ValidationError(
                    {
                        "winners_distribution": _(
                            "The sum of percentages must be exactly 100% (current: %(total)s%)."
                        )
                        % {"total": total}
                    }
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self):
        """
        Returns a timedelta based on duration_value and duration_unit.
        """
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        if self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        if self.duration_unit == "months":
            return timedelta(days=30 * self.duration_value)
        return timedelta(hours=self.duration_value)

    def create_lottery(self):
        # fortunaisk
        from fortunaisk.signals.lottery_signals import lottery_created

        """
        Creates a new Lottery from this AutoLottery and
        populates WinnerDistribution for that lottery.
        """
        # Dynamically retrieve the Lottery model
        Lottery = apps.get_model("fortunaisk", "Lottery")
        # Create the lottery
        new_lottery = Lottery.objects.create(
            ticket_price=self.ticket_price,
            start_date=timezone.now(),
            end_date=timezone.now() + self.get_duration_timedelta(),
            payment_receiver=self.payment_receiver,
            winner_count=self.winner_count,
            max_tickets_per_user=self.max_tickets_per_user,
            lottery_reference=Lottery.generate_unique_reference(),
            duration_value=self.duration_value,
            duration_unit=self.duration_unit,
            tax=self.tax,
        )
        logger.info(
            f"AutoLottery '{self.name}' created Lottery '{new_lottery.lottery_reference}'"
        )

        # Now create the WinnerDistribution entries
        WinnerDistribution = apps.get_model("fortunaisk", "WinnerDistribution")
        for rank, pct in enumerate(self.winners_distribution or [], start=1):
            # Ensure it's a Decimal with two decimal places
            pct_dec = Decimal(str(pct)).quantize(Decimal("0.01"))
            WinnerDistribution.objects.create(
                lottery_reference=new_lottery.lottery_reference,
                winner_rank=rank,
                winner_prize_distribution=pct_dec,
            )
        logger.debug(
            f"Created {len(self.winners_distribution or [])} WinnerDistribution entries "
            f"for lottery {new_lottery.lottery_reference}"
        )
        lottery_created.send(sender=self.__class__, instance=new_lottery)

        return new_lottery
