# fortunaisk/models/autolottery.py

# Django
from django.db import models


class AutoLottery(models.Model):
    """
    Represents a recurring lottery configuration.
    """

    FREQUENCY_UNITS = ["minutes", "hours", "days"]
    DURATION_UNITS = ["hours", "days", "months"]

    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    name = models.CharField(
        max_length=100, unique=True, verbose_name="AutoLottery Name"
    )
    frequency = models.PositiveIntegerField(verbose_name="Frequency Value")
    frequency_unit = models.CharField(
        max_length=10,
        choices=[(unit, unit.capitalize()) for unit in FREQUENCY_UNITS],
        default="days",
        verbose_name="Frequency Unit",
    )
    ticket_price = models.DecimalField(
        max_digits=20, decimal_places=2, verbose_name="Ticket Price (ISK)"
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Number of Winners"
    )
    winners_distribution = models.JSONField(
        default=list, blank=True, verbose_name="Winners Distribution"
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
