# fortunaisk/models.py
"""Models for the FortunaIsk lottery application."""

# Standard Library
import json
import logging
import random
import string

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from solo.models import SingletonModel

# Django
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

logger = logging.getLogger(__name__)


class LotterySettings(SingletonModel):
    """
    Global settings for the lottery application.
    Stores the default payment receiver (e.g. a corporation ID).
    """

    default_payment_receiver = models.CharField(
        max_length=100, default="Default Receiver"
    )

    def __str__(self):
        return "Lottery Settings"

    class Meta:
        verbose_name = "Lottery Settings"


class Lottery(models.Model):
    """
    Represents a single lottery.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.DecimalField(max_digits=20, decimal_places=2)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    payment_receiver = models.IntegerField()
    lottery_reference = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, default="active")
    winner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["-start_date"]

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def next_drawing_date(self):
        return self.end_date

    def save(self, *args, **kwargs):
        if not self.payment_receiver:
            # Apply default receiver from LotterySettings if not provided
            settings = LotterySettings.objects.get_or_create()[0]
            self.payment_receiver = settings.default_payment_receiver

        if not self.lottery_reference:
            self.lottery_reference = self.generate_unique_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_reference():
        """
        Generate a unique reference for the lottery.
        """
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def setup_periodic_task(self):
        """
        Sets up or updates a periodic task to process wallet tickets for all active lotteries.
        """
        task_name = "process_wallet_tickets_for_all_lotteries"
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=5, period=IntervalSchedule.MINUTES
        )
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets",
                "interval": schedule,
                "args": json.dumps([]),
            },
        )
        logger.info("Periodic task set for all active lotteries.")

    def delete(self, *args, **kwargs):
        """
        When a lottery is deleted, remove the periodic task if it exists.
        """
        task_name = "process_wallet_tickets_for_all_lotteries"
        PeriodicTask.objects.filter(name=task_name).delete()
        super().delete(*args, **kwargs)


class TicketPurchase(models.Model):
    """
    Represents a ticket purchased by a user for a specific lottery.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    lottery = models.ForeignKey(Lottery, on_delete=models.CASCADE)
    purchase_date = models.DateTimeField(default=timezone.now)
    amount = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lottery"], name="unique_user_lottery"
            )
        ]
        ordering = ["-purchase_date"]

    @property
    def date(self):
        return self.purchase_date


class Winner(models.Model):
    """
    Represents a winner of a lottery.
    """

    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.OneToOneField(TicketPurchase, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-won_at"]

    def __str__(self):
        return f"Winner: {self.character.character_name}"


def get_default_lottery():
    return None


class TicketAnomaly(models.Model):
    """
    Stores anomalies encountered when processing wallet entries that do not result in a valid TicketPurchase.
    """

    lottery = models.ForeignKey("Lottery", on_delete=models.CASCADE)
    character = models.ForeignKey(
        EveCharacter, on_delete=models.SET_NULL, null=True, blank=True
    )
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=255)
    payment_date = models.DateTimeField()
    amount = models.PositiveBigIntegerField(default=0)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"Anomaly for lottery {self.lottery.lottery_reference}: {self.reason}"
