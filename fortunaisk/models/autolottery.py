# fortunaisk/models/autolottery.py

# Django
from django.db import models  # type: ignore


class AutoLottery(models.Model):
    """
    Represents a recurring lottery configuration.
    """

    FREQUENCY_UNITS = [
        ("minutes", "Minutes"),
        ("hours", "Hours"),
        ("days", "Days"),
        ("months", "Months"),  # Added months to match usage
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
        default=1, verbose_name="Max Tickets Per User"
    )
    payment_receiver = models.IntegerField(verbose_name="Payment Receiver ID")

    def clean(self):
        if self.winners_distribution:
            if len(self.winners_distribution) != self.winner_count:
                raise ValueError(
                    "Mismatch between winners_distribution and winner_count."
                )
            if round(sum(self.winners_distribution), 2) != 100.0:
                raise ValueError("Sum of winners_distribution must equal 100.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self):
        """
        Calculate the duration of the lottery as a timedelta.
        """
        # Standard Library
        from datetime import timedelta

        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(
                days=30 * self.duration_value
            )  # Approximate 30 days per month.
        return timedelta(hours=self.duration_value)
