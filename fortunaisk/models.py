# fortunaisk/models.py

# Standard Library
import json
import logging
import random
import string
from datetime import timedelta

# Third Party
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask
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

    default_payment_receiver = models.IntegerField(
        default=0, help_text="ID du récepteur des paiements par défaut."
    )
    discord_webhook = models.URLField(null=True, blank=True)
    default_lottery_duration_value = models.PositiveIntegerField(default=24)
    default_lottery_duration_unit = models.CharField(
        max_length=10,
        choices=[
            ("hours", "Hours"),
            ("days", "Days"),
            ("months", "Months"),
        ],
        default="hours",
        help_text="Unité de durée par défaut pour les loteries.",
    )
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
        ("months", "Mois"),
    ]

    DURATION_UNITS = [
        ("hours", "Hours"),
        ("days", "Days"),
        ("months", "Months"),
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
    duration_value = models.PositiveIntegerField(help_text="Durée de la loterie.")
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNITS,
        default="hours",
        help_text="Unité de durée pour la loterie.",
    )
    payment_receiver = models.IntegerField(
        help_text="ID du récepteur des paiements par défaut."
    )
    winner_count = models.PositiveIntegerField(
        default=1, help_text="Nombre de gagnants par loterie."
    )
    winners_distribution_str = models.CharField(
        max_length=255,
        help_text="Liste des pourcentages pour chaque gagnant, séparés par des virgules. Exemple : '50,30,20' pour 3 gagnants.",
    )
    max_tickets_per_user = models.PositiveIntegerField(
        default=1, help_text="Nombre maximum de tickets par utilisateur."
    )

    def __str__(self):
        return self.name

    def get_duration_timedelta(self):
        """
        Convertit la durée en timedelta basé sur l'unité.
        """
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(days=30 * self.duration_value)  # Approximation
        else:
            return timedelta(hours=self.duration_value)  # Default

    def schedule_periodic_task(self):
        """
        Schedule a periodic task for this AutoLottery to create Lotteries based on its frequency and unit.
        """
        # Determine interval based on frequency_unit
        if self.frequency_unit == "minutes":
            interval, created = IntervalSchedule.objects.get_or_create(
                every=self.frequency,
                period=IntervalSchedule.MINUTES,
            )
        elif self.frequency_unit == "hours":
            interval, created = IntervalSchedule.objects.get_or_create(
                every=self.frequency,
                period=IntervalSchedule.HOURS,
            )
        elif self.frequency_unit == "days":
            interval, created = IntervalSchedule.objects.get_or_create(
                every=self.frequency,
                period=IntervalSchedule.DAYS,
            )
        elif self.frequency_unit == "months":
            # Approximate months as 30 days
            interval, created = IntervalSchedule.objects.get_or_create(
                every=30 * self.frequency,
                period=IntervalSchedule.DAYS,
            )
        else:
            logger.error(f"Unsupported frequency_unit: {self.frequency_unit}")
            return

        # Create or update PeriodicTask
        task_name = f"create_lottery_auto_{self.id}"
        task, created = PeriodicTask.objects.get_or_create(
            name=task_name,
            task="fortunaisk.tasks.create_lottery_from_auto",
            defaults={
                "interval": interval,
                "args": json.dumps([self.id]),
            },
        )
        if not created:
            # Update the interval and args
            task.interval = interval
            task.args = json.dumps([self.id])
            task.save()

        logger.info(f"Periodic task '{task_name}' scheduled.")

    def unschedule_periodic_task(self):
        """
        Remove the periodic task associated with this AutoLottery.
        """
        task_name = f"create_lottery_auto_{self.id}"
        PeriodicTask.objects.filter(name=task_name).delete()
        logger.info(f"Periodic task '{task_name}' unscheduled.")

    def create_first_lottery(self):
        """
        Create the first Lottery immediately upon creation of AutoLottery.
        """
        start_date = timezone.now()
        end_date = start_date + self.get_duration_timedelta()

        lottery = Lottery.objects.create(
            ticket_price=self.ticket_price,
            start_date=start_date,
            end_date=end_date,
            payment_receiver=self.payment_receiver,
            winner_count=self.winner_count,
            winners_distribution_str=self.winners_distribution_str,
            max_tickets_per_user=self.max_tickets_per_user,
            lottery_reference=Lottery.generate_unique_reference(),
            duration_value=self.duration_value,
            duration_unit=self.duration_unit,
        )

        logger.info(
            f"Created first Lottery '{lottery.lottery_reference}' from AutoLottery '{self.name}'."
        )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.create_first_lottery()
            self.schedule_periodic_task()
        else:
            self.schedule_periodic_task()

    def delete(self, *args, **kwargs):
        self.unschedule_periodic_task()
        super().delete(*args, **kwargs)


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
