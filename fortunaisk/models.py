# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask

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


class Lottery(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.PositiveBigIntegerField(default=10_000_000)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    payment_receiver = models.CharField(max_length=100, default="Default Receiver")
    lottery_reference = models.CharField(max_length=50, unique=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    winner_name = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["-start_date"]

    @property
    def is_active(self):
        """Check if the lottery is active."""
        return self.status == "active"

    @property
    def winner(self):
        """Return the winner's name if available."""
        return self.winner_name or "No Winner"

    @property
    def next_drawing_date(self):
        """Return the end date for the lottery."""
        return self.end_date

    def save(self, *args, **kwargs):
        """Generate lottery reference and create periodic task if needed."""
        if not self.lottery_reference:
            self.lottery_reference = f"LOTTERY-{self.start_date.strftime('%Y%m%d')}-{self.end_date.strftime('%Y%m%d')}"
        super().save(*args, **kwargs)
        self.setup_periodic_task()

    def setup_periodic_task(self):
        """Create or update the periodic task for checking wallet entries."""
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
    purchase_date = models.DateTimeField(default=timezone.now, auto_now_add=True)
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
        """Return the purchase date."""
        return self.purchase_date


class Winner(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.OneToOneField(TicketPurchase, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-won_at"]


class FortunaISKSettings(models.Model):
    ticket_price = models.PositiveBigIntegerField(default=10_000_000)
    next_drawing_date = models.DateTimeField(default=timezone.now)
    payment_receiver = models.CharField(max_length=100, default="Default Receiver")
    lottery_reference = models.CharField(max_length=50, unique=True, blank=True)

    class Meta:
        ordering = ["-next_drawing_date"]
