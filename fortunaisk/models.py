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

logger = logging.getLogger(__name__)


class Reward(models.Model):
    """
    Représente une récompense que les utilisateurs peuvent obtenir en fonction de leurs points.
    """

    name = models.CharField(max_length=100)
    description = models.TextField()
    points_required = models.PositiveIntegerField()

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """
    Étend le modèle User pour inclure des points et des récompenses.
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)
    rewards = models.ManyToManyField(Reward, blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"

    def check_rewards(self):
        """
        Vérifie et assigne les récompenses éligibles à l'utilisateur en fonction de ses points.
        """
        from .notifications import send_discord_notification  # Import interne

        eligible_rewards = Reward.objects.filter(
            points_required__lte=self.points
        ).exclude(id__in=self.rewards.all())
        for reward in eligible_rewards:
            self.rewards.add(reward)
            # Notifier l'utilisateur via Discord de la nouvelle récompense
            send_discord_notification(
                message=f"{self.user.username} a gagné la récompense {reward.name}!"
            )


class LotterySettings(SingletonModel):
    """
    Paramètres globaux pour l'application de loterie.
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


class AutoLottery(models.Model):
    """
    Représente une loterie automatique qui est créée selon une fréquence définie.
    """

    FREQUENCY_UNITS = [
        ("minutes", "Minutes"),
        ("hours", "Heures"),
        ("days", "Jours"),
    ]

    is_active = models.BooleanField(
        default=True, help_text="Active ou désactive la loterie automatique."
    )
    name = models.CharField(
        max_length=100, unique=True, help_text="Nom unique pour la loterie automatique."
    )
    frequency = models.PositiveIntegerField(
        help_text="Nombre de {unit} entre chaque création de loterie."
    )
    frequency_unit = models.CharField(
        max_length=10,
        choices=FREQUENCY_UNITS,
        default="days",
        help_text="Unité de fréquence pour la création de loterie.",
    )
    ticket_price = models.DecimalField(
        max_digits=20, decimal_places=2, help_text="Prix du ticket en ISK."
    )
    duration_hours = models.PositiveIntegerField(
        help_text="Durée de la loterie en heures."
    )
    payment_receiver = models.IntegerField(help_text="ID du récepteur des paiements.")
    winner_count = models.PositiveIntegerField(
        default=1, help_text="Nombre de gagnants par loterie."
    )
    winners_distribution_str = models.CharField(
        max_length=255,
        help_text="Liste des pourcentages pour chaque gagnant, séparés par des virgules. Exemple : '50,30,20' pour 3 gagnants.",
    )
    max_tickets_per_user = models.PositiveIntegerField(
        null=True, blank=True, help_text="Nombre maximum de tickets par utilisateur."
    )

    def __str__(self):
        return self.name


class Lottery(models.Model):
    """
    Représente une loterie unique.
    Supporte plusieurs gagnants avec une distribution donnée.
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
        help_text="Liste des pourcentages pour chaque gagnant, séparés par des virgules. Exemple : '50,30,20' pour 3 gagnants.",
    )
    max_tickets_per_user = models.PositiveIntegerField(null=True, blank=True)
    participant_count = models.PositiveIntegerField(default=0)
    total_pot = models.BigIntegerField(default=0)

    class Meta:
        ordering = ["-start_date"]
        permissions = [
            ("view_lotteryhistory", "Can view lottery history"),
            ("terminate_lottery", "Can terminate lottery"),
        ]

    @property
    def is_active(self):
        return self.status == "active"

    @property
    def next_drawing_date(self):
        return self.end_date

    def save(self, *args, **kwargs):
        if self.status == "completed" and self.pk:
            self.complete_lottery()
        if not self.lottery_reference:
            self.lottery_reference = self.generate_unique_reference()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_reference():
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def setup_periodic_task(self):
        """
        Configure ou met à jour une tâche périodique pour traiter les tickets de portefeuille pour toutes les loteries actives.
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
        logger.info("Tâche périodique configurée pour toutes les loteries actives.")

    def delete(self, *args, **kwargs):
        task_name = "process_wallet_tickets_for_all_lotteries"
        PeriodicTask.objects.filter(name=task_name).delete()
        super().delete(*args, **kwargs)

    def notify_discord(self, embed):
        from .notifications import send_discord_notification  # Import interne

        send_discord_notification(embed=embed)
        logger.info(f"Notification Discord envoyée: {embed}")

    def complete_lottery(self):
        """
        Termine la loterie, sélectionne les gagnants et envoie une notification à Discord.
        """
        if self.status != "active":
            return

        self.status = "completed"
        winners = self.select_winners()

        if winners:
            embed = {
                "title": "Loterie terminée !",
                "color": 15158332,  # Couleur rouge
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
                "color": 15158332,  # Couleur rouge
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
        Sélectionne les gagnants de la loterie en fonction du nombre de gagnants et de la distribution.
        """
        tickets = TicketPurchase.objects.filter(lottery=self)
        if not tickets.exists():
            return []

        winners = random.sample(list(tickets), min(self.winner_count, tickets.count()))
        for idx, winner in enumerate(winners):
            # Assurez-vous que la distribution est définie et correspond au nombre de gagnants
            if idx < len(self.winners_distribution):
                prize_percentage = self.winners_distribution[idx]
            else:
                prize_percentage = (
                    100 / self.winner_count
                )  # Répartir équitablement si distribution manquante

            prize_amount = self.total_pot * (prize_percentage / 100.0)
            Winner.objects.create(
                character=winner.character, ticket=winner, prize_amount=prize_amount
            )
            # Ajouter des points au gagnant
            profile, _ = UserProfile.objects.get_or_create(user=winner.user)
            profile.points += int(prize_amount / 1000)  # Exemple : 1 point par 1000 ISK
            profile.save()
            profile.check_rewards()

        return winners


@receiver(post_save, sender=Lottery)
def notify_discord_on_lottery_creation(sender, instance, created, **kwargs):
    if created:
        embed = {
            "title": "Nouvelle loterie créée !",
            "color": 3066993,  # Couleur verte
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
        "color": 15158332,  # Couleur rouge
        "fields": [
            {"name": "Référence", "value": instance.lottery_reference, "inline": False},
            {"name": "Statut", "value": "Terminé", "inline": False},
        ],
    }
    instance.notify_discord(embed)


class TicketPurchase(models.Model):
    """
    Représente un ticket acheté par un utilisateur pour une loterie spécifique.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    character = models.ForeignKey(EveCharacter, on_delete=models.CASCADE)
    lottery = models.ForeignKey(Lottery, on_delete=models.CASCADE)
    purchase_date = models.DateTimeField(default=timezone.now)
    amount = models.PositiveBigIntegerField()
    payment_id = models.CharField(
        max_length=255, unique=True, default="default_payment_id"
    )

    class Meta:
        ordering = ["-purchase_date"]

    @property
    def date(self):
        return self.purchase_date


class Winner(models.Model):
    """
    Représente un gagnant d'une loterie.
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
    """
    Représente des anomalies détectées dans les achats de tickets.
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
    payment_id = models.CharField(max_length=255, default="default_payment_id")

    class Meta:
        ordering = ["-recorded_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lottery", "payment_id"], name="unique_anomaly_for_payment"
            )
        ]
