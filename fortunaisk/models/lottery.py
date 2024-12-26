# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string
from datetime import timedelta
from decimal import Decimal

# Third Party
from celery import chain  # type: ignore

# Django
from django.db import models  # type: ignore
from django.db.models.signals import post_delete, post_save  # type: ignore
from django.dispatch import receiver  # type: ignore

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo  # type: ignore

# fortunaisk
from fortunaisk.models.ticket import TicketPurchase, Winner

logger = logging.getLogger(__name__)


class Lottery(models.Model):
    """
    Represents a unique instance of a lottery.
    Supports multiple winners based on distribution.
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
        null=True, blank=True, verbose_name="Max Tickets Per User"
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
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def clean(self):
        """
        Ensure winners_distribution is valid.
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
            return timedelta(days=30 * self.duration_value)  # Approximate
        return timedelta(hours=self.duration_value)

    def update_total_pot(self):
        """
        Update the total_pot based on number of tickets and ticket_price.
        """
        ticket_count = self.ticket_purchases.count()
        logger.debug(
            f"Lottery {self.lottery_reference} - Number of tickets: {ticket_count}"
        )
        self.total_pot = self.ticket_price * Decimal(ticket_count)
        self.save(update_fields=["total_pot"])
        logger.debug(
            f"Lottery {self.lottery_reference} - Total Pot updated: {self.total_pot} ISK"
        )

    def complete_lottery(self):
        if self.status != "active":
            logger.info(
                f"Lottery {self.lottery_reference} is not active. Current status: {self.status}"
            )
            return

        # Update total pot
        self.update_total_pot()
        logger.debug(
            f"Lottery {self.lottery_reference} - Total Pot recalculated: {self.total_pot} ISK"
        )

        if self.total_pot <= Decimal("0"):
            logger.error(
                f"Lottery {self.lottery_reference} has a total pot of {self.total_pot} ISK. Aborting prize distribution."
            )
            self.status = "completed"
            self.save(update_fields=["status"])
            return

        # Create a chain of tasks: first process wallet tickets, then finalize the lottery
        # fortunaisk
        from fortunaisk.tasks import finalize_lottery, process_wallet_tickets

        # Use chain to ensure order
        task_chain = chain(process_wallet_tickets.s(), finalize_lottery.si(self.id))
        task_chain.apply_async()
        logger.info(f"Task chain initiated for lottery {self.lottery_reference}.")

    def select_winners(self):
        tickets = TicketPurchase.objects.filter(lottery=self)
        ticket_ids = list(tickets.values_list("id", flat=True))
        if not ticket_ids:
            logger.info(f"No tickets found for lottery {self.lottery_reference}.")
            return []

        if len(ticket_ids) < self.winner_count:
            logger.warning(
                f"Not enough tickets to select {self.winner_count} winners for lottery {self.lottery_reference}. Selecting {len(ticket_ids)} winners."
            )
            selected_ids = ticket_ids  # All tickets are winners
        else:
            selected_ids = random.sample(ticket_ids, self.winner_count)

        winners = []

        for idx, ticket_id in enumerate(selected_ids):
            ticket = tickets.get(id=ticket_id)
            percentage_decimal = Decimal(str(self.winners_distribution[idx]))
            prize_amount = (self.total_pot * percentage_decimal) / Decimal("100")
            prize_amount = prize_amount.quantize(Decimal("0.01"))  # Ensure two decimals
            logger.debug(
                f"Calculated prize_amount: {prize_amount} ISK for winner: {ticket.user.username}"
            )
            winner = Winner.objects.create(
                character=ticket.character,
                ticket=ticket,
                prize_amount=prize_amount,
            )
            winners.append(winner)
            logger.info(
                f"Winner created: {winner.ticket.user.username} - {winner.prize_amount} ISK"
            )

        return winners

    def notify_discord(self, winners):
        if not winners:
            # Do nothing, notification is handled by the signal
            logger.info(f"No winners to notify for lottery {self.lottery_reference}.")
            return

        try:
            corporation = EveCorporationInfo.objects.get(
                corporation_id=self.payment_receiver
            )
            corp_name = corporation.corporation_name
        except EveCorporationInfo.DoesNotExist:
            corp_name = "Unknown Corporation"

        # Import locally to avoid circular imports
        # fortunaisk
        from fortunaisk.notifications import send_discord_notification

        for winner in winners:
            embed = {
                "title": "🎉🎉 **Congratulations to the Winner!** 🎉🎉",
                "description": f"We are thrilled to announce that **{winner.character.character_name}** has won the lottery **{self.lottery_reference}**! 🏆🥳",
                "color": 0xFFD700,  # Gold
                "thumbnail": {
                    "url": "https://static.vecteezy.com/system/resources/previews/008/505/855/non_2x/banknotes-rain-illustration-money-falling-png.png"  # Trophy image
                },
                "fields": [
                    {
                        "name": "🏆 **User**",
                        "value": f"{winner.ticket.user.username}",
                        "inline": True,
                    },
                    {
                        "name": "🛡️ **Character**",
                        "value": f"{winner.character.character_name}",
                        "inline": True,
                    },
                    {
                        "name": "💰 **Prize**",
                        "value": f"💰 **{winner.prize_amount:,.2f} ISK**",
                        "inline": True,
                    },
                    {
                        "name": "📅 **Win Date**",
                        "value": f"{winner.won_at.strftime('%Y-%m-%d %H:%M')}",
                        "inline": False,
                    },
                    {
                        "name": "🔑 **Payment Receiver**",
                        "value": corp_name,
                        "inline": False,
                    },
                ],
                "footer": {
                    "text": "Good luck to everyone! 🍀",
                    "icon_url": "https://media.istockphoto.com/id/505920740/fr/vectoriel/bonne-chance.jpg?s=612x612&w=0&k=20&c=_woE0-ItyfRZ2o-wXbe3N1TYqPhxxvTzBHPZkRdP7qw=",  # Footer icon
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
        logger.debug(
            f"post_save signal: TicketPurchase created for lottery {lottery.lottery_reference}"
        )
        lottery.update_total_pot()
        logger.info(
            f"post_save signal: Total pot updated for lottery {lottery.lottery_reference} after ticket purchase."
        )


@receiver(post_delete, sender=TicketPurchase)
def update_total_pot_on_ticket_delete(sender, instance, **kwargs):
    lottery = instance.lottery
    lottery.update_total_pot()
    logger.info(
        f"post_delete signal: Total pot updated for lottery {lottery.lottery_reference} after ticket deletion."
    )
