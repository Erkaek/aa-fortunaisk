# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string
from datetime import timedelta
from decimal import Decimal

# Third Party
from celery import chain

# Django
from django.db import models

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
# fortunaisk.models.ticket
from fortunaisk.models.ticket import TicketPurchase, Winner

logger = logging.getLogger(__name__)


class Lottery(models.Model):
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
        help_text="Price of a lottery ticket in ISK.",
    )
    start_date = models.DateTimeField(verbose_name="Start Date")
    end_date = models.DateTimeField(db_index=True, verbose_name="End Date")
    payment_receiver = models.ForeignKey(
        EveCorporationInfo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lotteries",
        verbose_name="Payment Receiver",
        help_text="The corporation receiving the payments.",
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
        help_text="List of percentage distributions for winners (sum must be 100).",
    )
    max_tickets_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Max Tickets Per User",
        help_text="Leave blank for unlimited.",
    )
    total_pot = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=0,
        verbose_name="Total Pot (ISK)",
        help_text="Total ISK pot from ticket purchases.",
    )
    duration_value = models.PositiveIntegerField(
        default=24,
        verbose_name="Duration Value",
        help_text="Numeric part of the lottery duration.",
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNITS,
        default="hours",
        verbose_name="Duration Unit",
        help_text="Unit of time for lottery duration.",
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Number of Winners"
    )

    class Meta:
        ordering = ["-start_date"]
        permissions = [
            ("view_lotteryhistory", "Can view lottery history"),
            ("terminate_lottery", "Can terminate a lottery"),
            ("admin_dashboard", "Can access the admin dashboard"),
        ]

    def __str__(self) -> str:
        return f"Lottery {self.lottery_reference} [{self.status}]"

    @staticmethod
    def generate_unique_reference() -> str:
        """
        Génère un identifiant unique (ex: LOTTERY-1234567890).
        """
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def clean(self):
        """
        Valide winners_distribution = 100 % et winners_distribution.length == winner_count
        """
        if self.winners_distribution:
            if len(self.winners_distribution) != self.winner_count:
                raise ValueError(
                    "Mismatch between winners_distribution and winner_count."
                )
            s = sum(self.winners_distribution)
            if abs(s - 100.0) > 0.001:
                raise ValueError("Sum of winners_distribution must be ~ 100.")

    def save(self, *args, **kwargs) -> None:
        self.clean()
        if not self.lottery_reference:
            self.lottery_reference = self.generate_unique_reference()
        super().save(*args, **kwargs)

    def get_duration_timedelta(self) -> timedelta:
        if self.duration_unit == "hours":
            return timedelta(hours=self.duration_value)
        elif self.duration_unit == "days":
            return timedelta(days=self.duration_value)
        elif self.duration_unit == "months":
            return timedelta(days=30 * self.duration_value)
        # par défaut
        return timedelta(hours=self.duration_value)

    def update_total_pot(self):
        """
        Recalcule la cagnotte en multipliant le ticket_price par le nombre de tickets vendus.
        """
        ticket_count = self.ticket_purchases.count()
        self.total_pot = self.ticket_price * Decimal(ticket_count)
        self.save(update_fields=["total_pot"])

    def complete_lottery(self):
        """
        Déclenche la finalisation de la loterie :
        - Met à jour la cagnotte
        - Lance la chain de tasks Celery (process_wallet_tickets puis finalize_lottery).
        """
        if self.status != "active":
            logger.info(
                f"Lottery {self.lottery_reference} not active. Current status: {self.status}"
            )
            return

        # Update pot
        self.update_total_pot()

        if self.total_pot <= Decimal("0"):
            logger.error(
                f"Lottery {self.lottery_reference} pot is 0. Marking completed."
            )
            self.status = "completed"
            self.save(update_fields=["status"])
            return

        # fortunaisk
        from fortunaisk.tasks import finalize_lottery, process_wallet_tickets

        chain(process_wallet_tickets.s(), finalize_lottery.si(self.id)).apply_async()
        logger.info(f"Task chain initiated for lottery {self.lottery_reference}.")

    def select_winners(self):
        """
        Choisit aléatoirement winner_count tickets (ou moins si pas assez de tickets).
        Crée un Winner pour chaque ticket gagnant.
        """
        tickets = TicketPurchase.objects.filter(lottery=self)
        ticket_ids = list(tickets.values_list("id", flat=True))
        if not ticket_ids:
            logger.info(f"No tickets in lottery {self.lottery_reference}.")
            return []

        if len(ticket_ids) < self.winner_count:
            logger.warning(f"Not enough tickets to select {self.winner_count} winners.")
            selected_ids = ticket_ids
        else:
            selected_ids = random.sample(ticket_ids, self.winner_count)

        winners = []
        for idx, ticket_id in enumerate(selected_ids):
            ticket = tickets.get(id=ticket_id)
            percentage_decimal = Decimal(str(self.winners_distribution[idx]))
            prize_amount = (self.total_pot * percentage_decimal) / Decimal("100")
            prize_amount = prize_amount.quantize(Decimal("0.01"))
            winner = Winner.objects.create(
                character=ticket.character,
                ticket=ticket,
                prize_amount=prize_amount,
            )
            winners.append(winner)

        return winners

    def notify_discord(self, winners):
        """
        Envoie une notification Discord pour chaque gagnant.
        """
        if not winners:
            logger.info(f"No winners to notify for lottery {self.lottery_reference}.")
            return
        try:
            corp_name = (
                self.payment_receiver.corporation_name
                if self.payment_receiver
                else "Unknown Corporation"
            )
        except Exception as ex:
            logger.warning(f"Error retrieving corporation_name: {ex}")
            corp_name = "Unknown Corporation"

        # fortunaisk
        from fortunaisk.notifications import send_discord_notification

        distribution_str = (
            ", ".join([f"{d}%" for d in self.winners_distribution]) or "N/A"
        )

        for winner in winners:
            embed = {
                "title": "🎉 **Congratulations to the Winner!** 🎉",
                "description": (
                    f"We are thrilled to announce that **{winner.character.character_name}** "
                    f"has won the lottery **{self.lottery_reference}**!"
                ),
                "color": 0xFFD700,
                "fields": [
                    {
                        "name": "User",
                        "value": f"{winner.ticket.user.username}",
                        "inline": True,
                    },
                    {
                        "name": "Character",
                        "value": f"{winner.character.character_name}",
                        "inline": True,
                    },
                    {
                        "name": "Prize",
                        "value": f"{winner.prize_amount:,.2f} ISK",
                        "inline": True,
                    },
                    {
                        "name": "Distribution",
                        "value": distribution_str,
                        "inline": False,
                    },
                    {
                        "name": "Win Date",
                        "value": f"{winner.won_at.strftime('%Y-%m-%d %H:%M')}",
                        "inline": False,
                    },
                    {"name": "Payment Receiver", "value": corp_name, "inline": False},
                ],
            }
            send_discord_notification(embed=embed)

    @property
    def participant_count(self):
        """
        Retourne le nombre total de TicketPurchase liés à cette loterie.
        """
        return self.ticket_purchases.count()

    @property
    def winners(self):
        """
        Permet d'accéder directement à tous les Winner liés à cette loterie
        via la relation Winner → TicketPurchase → Lottery.
        Ex : lottery.winners.all() dans un template.
        """
        # fortunaisk
        from fortunaisk.models import Winner

        return Winner.objects.filter(ticket__lottery=self)
