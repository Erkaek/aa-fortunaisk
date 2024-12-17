# fortunaisk/models.py

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


class Lottery(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.PositiveBigIntegerField(
        default=10000000, help_text="Price of a single ticket (in ISK)."
    )
    start_date = models.DateTimeField(
        default=timezone.now, help_text="Start date and time of the lottery."
    )
    end_date = models.DateTimeField(help_text="End date and time of the lottery.")
    payment_receiver = models.CharField(
        max_length=100,
        default="Default Receiver",
        help_text="Name of the character or corporation to which the ISK should be sent.",
    )
    lottery_reference = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Unique reference for the lottery.",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Status of the lottery.",
    )

    class Meta:
        verbose_name = "Lottery"
        verbose_name_plural = "Lotteries"
        ordering = ["-start_date"]

    def save(self, *args, **kwargs):
        if not self.lottery_reference:
            self.lottery_reference = (
                f"LOTTERY-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )
        super().save(*args, **kwargs)
        self.setup_periodic_task()

    def setup_periodic_task(self):
        """
        Configure or update the Celery Beat task to check ticket purchases.
        """
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=5,  # Frequency: every 5 minutes
            period=IntervalSchedule.MINUTES,
        )

        task_name = f"check_wallet_entries_fortunaisk_{self.lottery_reference}"

        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets",
                "interval": schedule,
                "args": json.dumps([self.id]),
                "description": f"Check wallet entries for lottery {self.lottery_reference}.",
                "enabled": True,
            },
        )

        if created:
            logger.info(f"Periodic task '{task_name}' created.")
        else:
            logger.info(f"Periodic task '{task_name}' updated.")


class TicketPurchaseManager(models.Manager):
    def setup_periodic_task(self, lottery_id):
        """
        Configure a periodic Celery Beat task to process ticket purchases for a specific lottery.
        """
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=5,  # Every 5 minutes
            period=IntervalSchedule.MINUTES,
        )

        task_name = f"process_ticket_purchases_{lottery_id}"

        # Check if the task exists to avoid duplicates
        if not PeriodicTask.objects.filter(name=task_name).exists():
            PeriodicTask.objects.create(
                interval=schedule,
                name=task_name,
                task="fortunaisk.tasks.process_wallet_tickets",
                args=json.dumps([lottery_id]),
                enabled=True,
            )
            logger.info(f"Celery Beat task '{task_name}' created.")
        else:
            logger.info(f"Celery Beat task '{task_name}' already exists.")


class TicketPurchase(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ticket_purchases"
    )
    character = models.ForeignKey(
        EveCharacter, on_delete=models.CASCADE, related_name="ticket_purchases"
    )
    lottery = models.ForeignKey(
        Lottery, on_delete=models.CASCADE, related_name="ticket_purchases"
    )
    date = models.DateTimeField(default=timezone.now)
    amount = models.PositiveBigIntegerField()

    objects = TicketPurchaseManager()  # Assign custom Manager

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lottery"], name="unique_user_lottery"
            )
        ]
        verbose_name = "Ticket Purchase"
        verbose_name_plural = "Ticket Purchases"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.character} - {self.lottery.lottery_reference}"


class Winner(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.OneToOneField(TicketPurchase, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)

    class Meta:
        permissions = [
            ("view_winner_custom", "Can view winners (custom permission)"),
            ("admin", "Can manage Fortunaisk winners"),
        ]
        verbose_name = "Winner"
        verbose_name_plural = "Winners"
        ordering = ["-won_at"]

    def __str__(self):
        return f"Winner: {self.character.character_name} - {self.ticket.lottery.lottery_reference}"


class FortunaISKSettings(models.Model):
    ticket_price = models.PositiveBigIntegerField(
        default=10000000, help_text="Price of a single ticket (in ISK)."
    )
    next_drawing_date = models.DateTimeField(
        default=timezone.now, help_text="Date and time of the next lottery drawing."
    )
    payment_receiver = models.CharField(
        max_length=100,
        default="Default Receiver",
        help_text="Name of the character or corporation to which the ISK should be sent.",
    )
    lottery_reference = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Unique reference for the lottery settings.",
    )

    class Meta:
        verbose_name = "FortunaISK Setting"
        verbose_name_plural = "FortunaISK Settings"
        ordering = ["-next_drawing_date"]

    def save(self, *args, **kwargs):
        if not self.lottery_reference:
            self.lottery_reference = (
                f"SETTING-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )
        super().save(*args, **kwargs)
        self.setup_periodic_task()

    def setup_periodic_task(self):
        """
        Configure or update the Celery Beat task to check ticket purchases.
        """
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=5,  # Frequency: every 5 minutes
            period=IntervalSchedule.MINUTES,
        )

        task_name = f"check_wallet_entries_fortunaisk_{self.lottery_reference}"

        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets",
                "interval": schedule,
                "args": json.dumps([self.id]),
                "description": f"Check wallet entries for lottery {self.lottery_reference}.",
                "enabled": True,
            },
        )

        if created:
            logger.info(f"Periodic task '{task_name}' created.")
        else:
            logger.info(f"Periodic task '{task_name}' updated.")

    def __str__(self):
        return f"Settings {self.lottery_reference}"
