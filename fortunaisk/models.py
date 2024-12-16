# Standard Library
import json

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.contrib.auth.models import User  # Modèle utilisateur standard de Django
from django.db import models
from django.utils import timezone

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter


class TicketPurchase(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="ticket_purchases"
    )
    character = models.ForeignKey(
        EveCharacter, on_delete=models.CASCADE, related_name="ticket_purchases"
    )
    lottery_reference = models.CharField(max_length=50)
    date = models.DateTimeField(default=timezone.now)
    amount = models.PositiveBigIntegerField()

    class Meta:
        unique_together = ("user", "lottery_reference")
        verbose_name = "Ticket Purchase"
        verbose_name_plural = "Ticket Purchases"

    def __str__(self):
        return f"{self.character} - {self.lottery_reference}"


class Winner(models.Model):
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    ticket = models.OneToOneField(TicketPurchase, on_delete=models.CASCADE)
    won_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ("add", "change", "delete")
        permissions = [
            ("view_winner_custom", "Can view winners (custom permission)"),
            ("admin", "Can manage Fortunaisk winners"),
        ]

    def __str__(self):
        return f"Winner: {self.character} - {self.ticket.lottery_reference}"


class FortunaISKSettings(models.Model):
    ticket_price = models.PositiveBigIntegerField(
        default=10000000, help_text="Price of a single ticket (in ISK)."
    )
    next_drawing_date = models.DateTimeField(
        help_text="Date and time of the next automatic drawing."
    )
    payment_receiver = models.CharField(
        max_length=100,
        default="Default Receiver",
        help_text="Name of the character or corporation to whom ISK should be sent.",
    )
    lottery_reference = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Unique reference for the current lottery.",
    )

    def save(self, *args, **kwargs):
        if not self.lottery_reference:
            self.lottery_reference = (
                f"LOTTERY-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            )
        super().save(*args, **kwargs)
        self.setup_periodic_task()  # Appelle la configuration des tâches après sauvegarde

    def setup_periodic_task(self):
        """
        Configure ou met à jour la tâche Celery Beat pour vérifier les achats de tickets.
        """
        # Crée ou récupère l'intervalle
        schedule, created = IntervalSchedule.objects.get_or_create(
            every=5,  # Fréquence : toutes les 5 minutes
            period=IntervalSchedule.MINUTES,
        )

        # Crée ou met à jour la tâche périodique
        PeriodicTask.objects.update_or_create(
            name="Check Wallet Entries for FortunaISK Tickets",
            defaults={
                "task": "fortunaisk.tasks.process_ticket_purchases",  # Chemin vers la tâche Celery
                "interval": schedule,
                "args": json.dumps([]),  # Aucune donnée spécifique
                "description": "Verifies wallet entries and updates ticket purchases.",
            },
        )

    def __str__(self):
        return "FortunaISK Settings"
