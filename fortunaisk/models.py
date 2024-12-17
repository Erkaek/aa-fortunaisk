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
        max_digits=15, decimal_places=2, default=10000000.00
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
            # Appliquer la valeur par défaut du receiver depuis LotterySettings
            settings = LotterySettings.objects.get_or_create()[0]
            self.payment_receiver = settings.default_payment_receiver

        if not self.lottery_reference:
            self.lottery_reference = f"LOTTERY-{self.start_date.strftime('%Y%m%d')}-{self.end_date.strftime('%Y%m%d')}"

        # Enregistrer la loterie
        super().save(*args, **kwargs)

        # Si la loterie est activée, configure la tâche périodique (une seule tâche pour toutes les loteries)
        if self.is_active:
            self.setup_periodic_task()

    def setup_periodic_task(self):
        # Une seule tâche périodique pour toutes les loteries actives
        task_name = "process_wallet_tickets_for_all_lotteries"
        schedule, _ = IntervalSchedule.objects.get_or_create(
            every=5, period=IntervalSchedule.MINUTES
        )

        # Créer ou mettre à jour la tâche périodique
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets_for_all_lotteries",
                "interval": schedule,
                "args": json.dumps(
                    []
                ),  # Pas besoin de passer un ID spécifique, la tâche gère toutes les loteries actives
            },
        )
        logger.info(f"Periodic task set for all active lotteries.")

    def delete(self, *args, **kwargs):
        task_name = "process_wallet_tickets_for_all_lotteries"
        PeriodicTask.objects.filter(name=task_name).delete()
        super().delete(*args, **kwargs)


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

    def __str__(self):
        return f"Winner: {self.character.character_name}"
