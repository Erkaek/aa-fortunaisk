# fortunaisk/models.py

# Standard Library
import json
import logging
import random
import string

# Third Party
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from solo.models import SingletonModel

# Django
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

from .notifications import send_discord_webhook  # Import depuis notifications.py

logger = logging.getLogger(__name__)


class LotterySettings(SingletonModel):
    """
    Global settings for the lottery application.
    """

    default_payment_receiver = models.CharField(
        max_length=100, default="Default Receiver"
    )
    discord_webhook = models.URLField(null=True, blank=True)
    default_lottery_duration_hours = models.PositiveIntegerField(default=24)
    default_max_tickets_per_user = models.PositiveIntegerField(default=1)

    def __str__(self):
        return "Lottery Settings"

    class Meta:
        verbose_name = "Lottery Settings"


class Lottery(models.Model):
    """
    Represents a single lottery.
    Supports multiple winners with a given distribution.
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
    lottery_reference = models.CharField(
        max_length=20, unique=True, blank=True, null=True
    )
    status = models.CharField(max_length=20, default="active")
    winner_count = models.PositiveIntegerField(default=1)
    winners_distribution = models.JSONField(default=list, blank=True)
    winners_distribution_str = models.CharField(
        max_length=255,
        blank=True,
        help_text="List of percentages for each winner, separated by commas. Example: '50,30,20' for 3 winners.",
    )
    max_tickets_per_user = models.PositiveIntegerField(null=True, blank=True)
    participant_count = models.PositiveIntegerField(default=0)
    total_pot = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-start_date"]

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def next_drawing_date(self):
        return self.end_date

    def save(self, *args, **kwargs):
        if self.status == "completed" and self.pk:
            self.complete_lottery()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_reference():
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def setup_periodic_task(self):
        """
        Sets up or updates a periodic task to process wallet tickets for all active lotteries.
        """
        task_name = "process_wallet_tickets_for_all_lotteries"
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="*/5",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="UTC",
        )
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets",
                "crontab": schedule,
                "args": json.dumps([]),
            },
        )
        logger.info("Periodic task set for all active lotteries.")

    def delete(self, *args, **kwargs):
        task_name = "process_wallet_tickets_for_all_lotteries"
        PeriodicTask.objects.filter(name=task_name).delete()
        super().delete(*args, **kwargs)

    def notify_discord(self, embed):
        send_discord_webhook(embed)
        logger.info(f"Notification Discord envoyée: {embed}")

    def complete_lottery(self):
        """
        Completes the lottery, selects winners, and sends a notification to Discord.
        """
        if self.status != "active":
            return

        self.status = "completed"
        winners = self.select_winners()

        if winners:
            embed = {
                "title": "Loterie terminée !",
                "color": 15158332,  # Red color
                "fields": [
                    {
                        "name": "Référence",
                        "value": self.lottery_reference,
                        "inline": False,
                    },
                    {"name": "Statut", "value": "Terminé", "inline": False},
                    {
                        "name": "Gagnants",
                        "value": "\n".join(
                            [str(winner.character.character_name) for winner in winners]
                        ),
                        "inline": False,
                    },
                ],
            }
        else:
            embed = {
                "title": "Loterie terminée !",
                "color": 15158332,  # Red color
                "fields": [
                    {
                        "name": "Référence",
                        "value": self.lottery_reference,
                        "inline": False,
                    },
                    {"name": "Statut", "value": "Terminé", "inline": False},
                    {"name": "Gagnants", "value": "Aucun gagnant", "inline": False},
                ],
            }

        self.notify_discord(embed)
        self.save()

    def select_winners(self):
        """
        Selects winners for the lottery based on the number of winners and distribution.
        """
        tickets = TicketPurchase.objects.filter(lottery=self)
        if not tickets.exists():
            return []

        winners = random.sample(list(tickets), min(self.winner_count, tickets.count()))
        for idx, winner in enumerate(winners):
            prize_amount = self.total_pot * (self.winners_distribution[idx] / 100)
            Winner.objects.create(
                character=winner.character, ticket=winner, prize_amount=prize_amount
            )

        return winners


@receiver(post_save, sender=Lottery)
def notify_discord_on_lottery_creation(sender, instance, created, **kwargs):
    if created:
        embed = {
            "title": "Nouvelle loterie créée !",
            "color": 3066993,  # Green color
            "fields": [
                {
                    "name": "Référence",
                    "value": instance.lottery_reference,
                    "inline": False,
                },
                {
                    "name": "Prix du ticket",
                    "value": f"{instance.ticket_price} ISK",
                    "inline": False,
                },
                {
                    "name": "Date de fin",
                    "value": instance.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": False,
                },
                {
                    "name": "Récepteur des paiements",
                    "value": str(instance.payment_receiver),
                    "inline": False,
                },
            ],
        }
        instance.notify_discord(embed)


@receiver(pre_delete, sender=Lottery)
def notify_discord_on_lottery_deletion(sender, instance, **kwargs):
    embed = {
        "title": "Loterie terminée !",
        "color": 15158332,  # Red color
        "fields": [
            {"name": "Référence", "value": instance.lottery_reference, "inline": False},
            {"name": "Statut", "value": "Terminé", "inline": False},
        ],
    }
    instance.notify_discord(embed)


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
        ordering = ["-purchase_date"]

    @property
    def date(self):
        return self.purchase_date


class Winner(models.Model):
    """
    Represents a winner of a lottery.
    """

    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.ForeignKey(TicketPurchase, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)
    prize_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    class Meta:
        ordering = ["-won_at"]

    def __str__(self):
        return f"Winner: {self.character.character_name}"


class TicketAnomaly(models.Model):
    lottery = models.ForeignKey("Lottery", on_delete=models.CASCADE)
    character = models.ForeignKey(
        EveCharacter, on_delete=models.SET_NULL, null=True, blank=True
    )
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    reason = models.CharField(max_length=255)
    payment_date = models.DateTimeField()
    amount = models.PositiveBigIntegerField(default=0)
    recorded_at = models.DateTimeField(default=timezone.now)
    payment_id = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-recorded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lottery", "payment_id"], name="unique_anomaly_for_payment"
            )
        ]


class WebhookConfiguration(models.Model):
    webhook_url = models.URLField("URL du Webhook")

    class Meta:
        verbose_name = "Configuration du Webhook"

    def __str__(self):
        return self.webhook_url


class AutoLottery(models.Model):
    name = models.CharField(max_length=100, unique=True)
    frequency = models.PositiveIntegerField(default=1)
    frequency_unit = models.CharField(
        max_length=10,
        choices=[
            ("minute", "Minutes"),
            ("hour", "Hours"),
            ("day", "Days"),
            ("week", "Weeks"),
        ],
        default="day",
    )
    ticket_price = models.DecimalField(max_digits=20, decimal_places=2)
    duration_hours = models.PositiveIntegerField(default=24)
    payment_receiver = models.IntegerField()
    winner_count = models.PositiveIntegerField(default=1)
    winners_distribution_str = models.CharField(
        max_length=255,
        blank=True,
        help_text="List of percentages for each winner, separated by commas. Example: '50,30,20' for 3 winners.",
    )
    max_tickets_per_user = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Automatic Lottery"
        verbose_name_plural = "Automatic Lotteries"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            from .tasks import create_lottery_from_auto

            create_lottery_from_auto(self.id)
        self.setup_periodic_task()

    def setup_periodic_task(self):
        if not self.is_active:
            PeriodicTask.objects.filter(name=f"AutoLottery_{self.id}").delete()
            return
        cron_minute = "0"
        cron_hour = "0"
        cron_day_of_week = "*"
        cron_day_of_month = "*"
        cron_month_of_year = "*"
        if self.frequency_unit == "minute":
            cron_minute = f"*/{self.frequency}"
        elif self.frequency_unit == "hour":
            cron_hour = f"*/{self.frequency}"
        elif self.frequency_unit == "day":
            cron_day_of_month = f"*/{self.frequency}"
        elif self.frequency_unit == "week":
            cron_day_of_week = f"*/{self.frequency}"
        elif self.frequency_unit == "month":
            cron_month_of_year = f"*/{self.frequency}"
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute=cron_minute,
            hour=cron_hour,
            day_of_week=cron_day_of_week,
            day_of_month=cron_day_of_month,
            month_of_year=cron_month_of_year,
            timezone="UTC",
        )
        task_name = f"AutoLottery_{self.id}"
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.create_lottery_from_auto",
                "crontab": schedule,
                "args": json.dumps([self.id]),
            },
        )
        logger.info(f"Periodic task '{task_name}' set for AutoLottery '{self.name}'.")

    def delete(self, *args, **kwargs):
        task_name = f"AutoLottery_{self.id}"
        PeriodicTask.objects.filter(name=task_name).delete()
        super().delete(*args, **kwargs)


@receiver(pre_delete, sender=AutoLottery)
def delete_periodic_task(sender, instance, **kwargs):
    task_name = f"AutoLottery_{instance.id}"
    PeriodicTask.objects.filter(name=task_name).delete()
