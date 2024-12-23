# fortunaisk/models/autolottery.py

# Standard Library
from datetime import timedelta

# Django
from django.db import models
from django.utils import timezone

from .lottery import Lottery


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

    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="Activates or deactivates the automatic lottery schedule.",
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="AutoLottery Name",
        help_text="Unique name for the automatic lottery.",
    )
    frequency = models.PositiveIntegerField(
        verbose_name="Frequency Value",
        help_text="Number of {unit} between each creation of a new lottery.",
    )
    frequency_unit = models.CharField(
        max_length=10,
        choices=FREQUENCY_UNITS,
        default="days",
        verbose_name="Frequency Unit",
        help_text="The unit of frequency for auto-creating lotteries.",
    )
    ticket_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Ticket Price (ISK)",
        help_text="Price of a single ticket in ISK.",
    )
    duration_value = models.PositiveIntegerField(
        verbose_name="Lottery Duration Value",
        help_text="Duration of the lottery (numeric part).",
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNITS,
        default="hours",
        verbose_name="Lottery Duration Unit",
        help_text="The unit of time for the lottery duration.",
    )
    payment_receiver = models.IntegerField(
        verbose_name="Payment Receiver ID",
        help_text="ID of the default payment receiver.",
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Number of Winners"
    )
    winners_distribution = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Winners Distribution",
        help_text="Percentage distribution for the winners (sum must be 100).",
    )
    max_tickets_per_user = models.PositiveIntegerField(
        default=1, verbose_name="Max Tickets per User"
    )

    def __str__(self) -> str:
        return self.name

    def get_duration_timedelta(self) -> timedelta:
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            # approximate 30 days
            return timedelta(days=30 * self.duration_value)
        return timedelta(hours=self.duration_value)

    def schedule_periodic_task(self) -> None:
        # Logique de planification des tâches périodiques
        pass

    def unschedule_periodic_task(self) -> None:
        # Logique de suppression des tâches périodiques
        pass

    def create_first_lottery(self) -> None:
        start_date = timezone.now()
        end_date = start_date + self.get_duration_timedelta()

        new_lottery = Lottery.objects.create(
            ticket_price=self.ticket_price,
            start_date=start_date,
            end_date=end_date,
            payment_receiver=self.payment_receiver,
            winner_count=self.winner_count,
            winners_distribution=self.winners_distribution,
            max_tickets_per_user=self.max_tickets_per_user,
            lottery_reference=Lottery.generate_unique_reference(),
            duration_value=self.duration_value,
            duration_unit=self.duration_unit,
        )
        # Logique supplémentaire si nécessaire

    def save(self, *args: Any, **kwargs: Any) -> None:
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.create_first_lottery()
            self.schedule_periodic_task()
        else:
            if self.is_active:
                self.schedule_periodic_task()
            else:
                self.unschedule_periodic_task()

    def delete(self, *args: Any, **kwargs: Any) -> None:
        self.unschedule_periodic_task()
        super().delete(*args, **kwargs)
