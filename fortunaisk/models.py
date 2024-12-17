# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render
from django.db.models import Count

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

logger = logging.getLogger(__name__)


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

    class Meta:
        ordering = ["-start_date"]

    def save(self, *args, **kwargs):
        if not self.lottery_reference:
            self.lottery_reference = (
                f"LOTTERY-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )
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


def get_default_lottery():
    lottery, _ = Lottery.objects.get_or_create(
        lottery_reference="DEFAULT-LOTTERY",
        defaults={
            "ticket_price": 10_000_000,
            "start_date": timezone.now(),
            "end_date": timezone.now() + timezone.timedelta(days=30),
        },
    )
    return lottery.id


class TicketPurchase(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    lottery = models.ForeignKey(Lottery, on_delete=models.CASCADE)

    purchase_date = models.DateTimeField(auto_now_add=True)
    amount = models.PositiveBigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'lottery'], name='unique_user_lottery')
        ]
        ordering = ["-purchase_date"]


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
