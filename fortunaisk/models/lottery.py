# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string
from datetime import timedelta
from decimal import Decimal

# Django
from django.db import models
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models.ticket import TicketPurchase, Winner

logger = logging.getLogger(__name__)


class Lottery(models.Model):
    """
    Represents a single lottery instance.
    Supports multiple winners based on a distribution.
    """

    DURATION_UNITS = [
        ("hours", "Hours"),
        ("days", "Days"),
        ("months", "Months"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Ticket Price (ISK)",
        help_text="Price of a single lottery ticket in ISK.",
    )
    start_date = models.DateTimeField(verbose_name="Start Date")
    end_date = models.DateTimeField(db_index=True, verbose_name="End Date")
    payment_receiver = models.IntegerField(
        db_index=True,
        verbose_name="Payment Receiver ID",
        help_text="Corporation or character ID that receives ISK payments.",
    )
    lottery_reference = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Lottery Reference",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
        verbose_name="Lottery Status",
    )
    winners_distribution = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Winners Distribution",
        help_text="List of percentage splits for winners (sum must be 100).",
    )
    max_tickets_per_user = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Max Tickets Per User"
    )
    total_pot = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=0,
        verbose_name="Total Pot (ISK)",
        help_text="Cumulative ISK pot from ticket purchases.",
    )
    duration_value = models.PositiveIntegerField(
        default=24,
        verbose_name="Duration Value",
        help_text="Numeric value of the lottery duration.",
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNITS,
        default="hours",
        verbose_name="Duration Unit",
        help_text="Unit of time for the lottery duration.",
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Number of Winners"
    )

    class Meta:
        ordering = ["-start_date"]
        permissions = [
            ("view_lotteryhistory", "Can view lottery history"),
            ("terminate_lottery", "Can terminate lottery"),
            ("admin_dashboard", "Can access admin dashboard"),
        ]

    def __str__(self) -> str:
        return f"Lottery {self.lottery_reference} [{self.status}]"

    @staticmethod
    def generate_unique_reference() -> str:
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def clean(self):
        """
        Ensures that the winners_distribution is valid.
        """
        if self.winners_distribution:
            if len(self.winners_distribution) != self.winner_count:
                logger.error("Mismatch between winners_distribution and winner_count.")
                raise ValueError(
                    "Mismatch between winners_distribution and winner_count."
                )
            total_percentage = sum(self.winners_distribution)
            logger.debug(f"Sum of winners_distribution: {total_percentage}")
            if round(total_percentage, 2) != 100.0:
                logger.error("Sum of winners_distribution must equal 100.")
                raise ValueError("Sum of winners_distribution must equal 100.")

    def save(self, *args, **kwargs) -> None:
        self.clean()
        if not self.lottery_reference:
            self.lottery_reference = self.generate_unique_reference()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self) -> timedelta:
        """
        Calculate the duration of the lottery as a timedelta.
        """
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(
                days=30 * self.duration_value
            )  # Approximate 30 days per month.
        return timedelta(hours=self.duration_value)

    def update_total_pot(self):
        """
        Update the total_pot based on the number of tickets and ticket price.
        """
        ticket_count = self.ticket_purchases.count()
        self.total_pot = self.ticket_price * Decimal(ticket_count)
        self.save(update_fields=["total_pot"])
        logger.debug(
            f"Loterie {self.lottery_reference} - Total Pot mis à jour: {self.total_pot} ISK"
        )

    def complete_lottery(self):
        if self.status != "active":
            logger.info(
                f"Loterie {self.lottery_reference} n'est pas active. Statut actuel: {self.status}"
            )
            return

        # Recalculer total_pot avant de sélectionner les gagnants
        self.update_total_pot()
        logger.debug(
            f"Loterie {self.lottery_reference} - Total Pot recalculé: {self.total_pot} ISK"
        )

        if self.total_pot <= Decimal("0"):
            logger.error(
                f"Loterie {self.lottery_reference} a un pot total de {self.total_pot} ISK. Abandon de la distribution des prix."
            )
            self.status = "completed"
            self.save(update_fields=["status"])
            return

        self.status = "completed"
        self.save(update_fields=["status"])
        winners = self.select_winners()
        self.notify_discord(winners)
        self.save()

    def select_winners(self):
        tickets = TicketPurchase.objects.filter(lottery=self)
        if not tickets.exists():
            logger.info(
                f"Aucun ticket trouvé pour la loterie {self.lottery_reference}."
            )
            return []

        winners = []
        selected_ticket_ids = set()
        for idx, percentage in enumerate(self.winners_distribution):
            if idx >= self.winner_count:
                break
            # Assurer des gagnants uniques
            available_tickets = tickets.exclude(id__in=selected_ticket_ids)
            if not available_tickets.exists():
                logger.warning(
                    f"Plus de tickets disponibles pour la loterie {self.lottery_reference}."
                )
                break
            random_ticket = available_tickets.order_by("?").first()
            if random_ticket:
                selected_ticket_ids.add(random_ticket.id)
                # Conversion de percentage en Decimal
                percentage_decimal = Decimal(str(percentage))
                prize_amount = (self.ticket_price * percentage_decimal) / Decimal("100")
                prize_amount = prize_amount.quantize(
                    Decimal("0.01")
                )  # Ensure two decimal places
                logger.debug(
                    f"Calculé prize_amount: {prize_amount} ISK pour le gagnant: {random_ticket.user.username}"
                )
                winner = Winner.objects.create(
                    character=random_ticket.character,
                    ticket=random_ticket,
                    prize_amount=prize_amount,
                )
                winners.append(winner)
                logger.info(
                    f"Gagnant créé: {winner.ticket.user.username} - {winner.prize_amount} ISK"
                )

        return winners

    def notify_discord(self, winners):
        if not winners:
            # Ne rien faire ici, la notification est gérée par le signal
            logger.info(
                f"Aucun gagnant à notifier pour la loterie {self.lottery_reference}."
            )
            return

        # Import local pour éviter l'import circulaire
        # fortunaisk
        from fortunaisk.notifications import send_discord_notification

        for winner in winners:
            embed = {
                "title": "🎉🎉 **Félicitations au Gagnant!** 🎉🎉",
                "description": f"Nous sommes ravis d'annoncer que **{winner.character.character_name}** a remporté la loterie **{self.lottery_reference}** ! 🏆🥳",
                "color": 0xFFD700,  # Or
                "thumbnail": {
                    "url": "https://static.vecteezy.com/system/resources/previews/008/505/855/non_2x/banknotes-rain-illustration-money-falling-png.png"  # Image de trophée
                },
                "fields": [
                    {
                        "name": "🏆 **Utilisateur**",
                        "value": f"{winner.ticket.user.username}",
                        "inline": True,
                    },
                    {
                        "name": "🛡️ **Personnage**",
                        "value": f"{winner.character.character_name}",
                        "inline": True,
                    },
                    {
                        "name": "💰 **Prix**",
                        "value": f"💰 **{winner.prize_amount:,.2f} ISK**",
                        "inline": True,
                    },
                    {
                        "name": "📅 **Date de Gain**",
                        "value": f"{winner.won_at.strftime('%Y-%m-%d %H:%M')}",
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": "Bonne chance à tous! 🍀",
                    "icon_url": "https://media.istockphoto.com/id/505920740/fr/vectoriel/bonne-chance.jpg?s=612x612&w=0&k=20&c=_woE0-ItyfRZ2o-wXbe3N1TYqPhxxvTzBHPZkRdP7qw=",  # Icône du footer
                },
                "timestamp": winner.won_at.isoformat(),
            }
            send_discord_notification(embed=embed)

    @property
    def participant_count(self):
        """Returns the number of participants in the lottery."""
        return self.ticket_purchases.count()


@receiver(post_save, sender=TicketPurchase)
def update_total_pot_on_ticket_purchase(sender, instance, created, **kwargs):
    if created:
        lottery = instance.lottery
        lottery.update_total_pot()
        logger.info(
            f"Signal post_save: Updated total_pot for Lottery {lottery.lottery_reference} after ticket purchase."
        )


@receiver(post_delete, sender=TicketPurchase)
def update_total_pot_on_ticket_delete(sender, instance, **kwargs):
    lottery = instance.lottery
    lottery.update_total_pot()
