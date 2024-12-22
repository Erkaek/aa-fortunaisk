# fortunaisk/models/lottery.py
import logging
import random
import string
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

class Lottery(models.Model):
    """
    Represents a single lottery instance.
    Supports multiple winners based on a distribution.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    ticket_price = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        verbose_name="Ticket Price (ISK)",
        help_text="Price of a single lottery ticket in ISK."
    )
    start_date = models.DateTimeField(verbose_name="Start Date")
    end_date = models.DateTimeField(db_index=True, verbose_name="End Date")
    payment_receiver = models.IntegerField(
        db_index=True,
        verbose_name="Payment Receiver ID",
        help_text="Corporation or character ID that receives ISK payments."
    )
    lottery_reference = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Lottery Reference"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
        verbose_name="Lottery Status"
    )
    winners_distribution = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Winners Distribution",
        help_text="List of percentage splits for winners (sum must be 100)."
    )
    max_tickets_per_user = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Max Tickets Per User"
    )
    participant_count = models.PositiveIntegerField(
        default=0,
        verbose_name="Participant Count"
    )
    total_pot = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=0,
        verbose_name="Total Pot (ISK)",
        help_text="Cumulative ISK pot from ticket purchases."
    )
    duration_value = models.PositiveIntegerField(
        default=24,
        verbose_name="Lottery Duration Value",
        help_text="Duration numeric part (e.g., 24 hours)."
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=[
            ("hours", "Hours"),
            ("days", "Days"),
            ("months", "Months"),
        ],
        default="hours",
        verbose_name="Lottery Duration Unit"
    )
    winner_count = models.PositiveIntegerField(
        default=1,
        verbose_name="Number of Winners"
    )

    class Meta:
        ordering = ["-start_date"]
        permissions = [
            ("view_lotteryhistory", "Can view lottery history"),
            ("terminate_lottery", "Can terminate lottery"),
        ]

    def __str__(self) -> str:
        return f"Lottery {self.lottery_reference} [{self.status}]"

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def next_drawing_date(self) -> timezone.datetime:
        return self.end_date

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
        # Additional logic for notifications or signals can happen via signals.py

    @staticmethod
    def generate_unique_reference() -> str:
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def notify_discord(self, embed: Dict[str, Any]) -> None:
        """
        Send a Discord notification with an embed.
        """
        from fortunaisk.notifications import send_discord_notification
        send_discord_notification(embed=embed)
        logger.info(f"Discord notification sent: {embed}")

    def complete_lottery(self) -> None:
        """
        Complete the lottery, select winners, send a Discord notification.
        """
        if self.status != "active":
            return

        self.status = "completed"
        from fortunaisk.models import TicketPurchase, Winner
        winners = self.select_winners()

        if winners:
            embed = {
                "title": "Lottery Completed!",
                "color": 15158332,  # Red color
                "fields": [
                    {
                        "name": "Reference",
                        "value": self.lottery_reference,
                        "inline": False,
                    },
                    {"name": "Status", "value": "Completed", "inline": False},
                    {
                        "name": "Winners",
                        "value": "\n".join(
                            [str(winner.character.character_name) for winner in winners if winner.character]
                        ),
                        "inline": False,
                    },
                ],
            }
        else:
            embed = {
                "title": "Lottery Completed!",
                "color": 15158332,
                "fields": [
                    {
                        "name": "Reference",
                        "value": self.lottery_reference,
                        "inline": False,
                    },
                    {"name": "Status", "value": "Completed", "inline": False},
                    {"name": "Winners", "value": "No winners", "inline": False},
                ],
            }

        self.notify_discord(embed)
        self.save()

    def select_winners(self) -> List["Winner"]:
        """
        Selects winners based on the number of winners and the distribution.
        Returns the list of Winner objects created.
        """
        from fortunaisk.models import TicketPurchase, Winner, UserProfile

        tickets = TicketPurchase.objects.filter(lottery=self)
        if not tickets.exists():
            return []

        winners: List[Winner] = []
        distributions = self.winners_distribution

        for idx, percentage in enumerate(distributions):
            if idx >= self.winner_count:
                break
            # pick a random ticket
            random_ticket: Optional[TicketPurchase] = tickets.order_by("?").first()
            if random_ticket and random_ticket not in [w.ticket for w in winners]:
                # create the winner
                new_winner = Winner.objects.create(
                    character=random_ticket.character,
                    ticket=random_ticket,
                    prize_amount=self.total_pot * (percentage / 100.0)
                )
                winners.append(new_winner)

                # add points to user
                profile, _ = UserProfile.objects.get_or_create(user=random_ticket.user)
                # example ratio: 1 point per 1000 ISK
                profile.points += int(new_winner.prize_amount / 1000)
                profile.save()
                profile.check_rewards()

        return winners
