# Standard Library
import json
import logging
from decimal import Decimal

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from solo.models import SingletonModel  # Singleton pour paramètres globaux

# Django
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

logger = logging.getLogger(__name__)


def get_default_lottery():
    """Return the ID of the default lottery, creating one if it doesn't exist."""
    lottery, _ = Lottery.objects.get_or_create(
        lottery_reference="DEFAULT-LOTTERY",
        defaults={
            "ticket_price": 10_000_000,
            "start_date": timezone.now(),
            "end_date": timezone.now() + timezone.timedelta(days=30),
        },
    )
    return lottery.id


class LotterySettings(SingletonModel):
    """Global settings for the lottery app."""

    default_payment_receiver = models.CharField(
        max_length=100, default="Default Receiver"
    )

    def __str__(self):
        return "Lottery Settings"

    class Meta:
        verbose_name = "Lottery Settings"


class Lottery(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal("10000000.00")
    )
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    payment_receiver = models.CharField(max_length=100, blank=True)
    lottery_reference = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    winner_name = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def winner(self):
        return self.winner_name or "No Winner"

    @property
    def next_drawing_date(self):
        return self.end_date

    def save(self, *args, **kwargs):
        if not self.payment_receiver:
            # Appliquer la valeur par défaut depuis LotterySettings
            settings = LotterySettings.objects.get_or_create()[0]
            self.payment_receiver = settings.default_payment_receiver

        if not self.lottery_reference:
            self.lottery_reference = f"LOTTERY-{self.start_date.strftime('%Y%m%d')}-{self.end_date.strftime('%Y%m%d')}"

        super().save(*args, **kwargs)
        self.setup_periodic_task()

    def setup_periodic_task(self):
        task_name = f"check_wallet_entries_{self.lottery_reference}"
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=5, period=IntervalSchedule.MINUTES
        )
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets",
                "interval": schedule,
                "args": json.dumps([self.id]),
            },
        )


class TicketPurchase(models.Model):
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
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.OneToOneField(TicketPurchase, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-won_at"]
