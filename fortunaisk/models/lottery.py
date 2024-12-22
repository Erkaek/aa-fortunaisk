# fortunaisk/models/lottery.py

# Standard Library
import logging
import random
import string

# Django
from django.db import models

# fortunaisk
from fortunaisk.models.ticket import TicketPurchase, Winner
from fortunaisk.models.user_profile import UserProfile

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
    participant_count = models.PositiveIntegerField(
        default=0, verbose_name="Participant Count"
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
        verbose_name="Lottery Duration Value",
        help_text="Duration numeric part (e.g., 24 hours).",
    )
    duration_unit = models.CharField(
        max_length=10,
        choices=[("hours", "Hours"), ("days", "Days"), ("months", "Months")],
        default="hours",
        verbose_name="Lottery Duration Unit",
    )
    winner_count = models.PositiveIntegerField(
        default=1, verbose_name="Number of Winners"
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
    def next_drawing_date(self):
        return self.end_date

    @staticmethod
    def generate_unique_reference() -> str:
        while True:
            reference = f"LOTTERY-{''.join(random.choices(string.digits, k=10))}"
            if not Lottery.objects.filter(lottery_reference=reference).exists():
                return reference

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)
        # Additional logic for notifications or signals can happen via signals.py

    def notify_discord(self, embed: dict) -> None:
        # fortunaisk
        from fortunaisk.notifications import send_discord_notification

        send_discord_notification(embed=embed)
        logger.info(f"Discord notification sent: {embed}")

    def complete_lottery(self) -> None:
        if self.status != "active":
            return

        self.status = "completed"
        winners = self.select_winners()
        if winners:
            embed = {
                "title": "Lottery Completed!",
                "color": 15158332,  # red color
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
                            w.character.character_name for w in winners if w.character
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

    def select_winners(self):
        tickets = TicketPurchase.objects.filter(lottery=self)
        if not tickets.exists():
            return []

        winners = []
        distributions = self.winners_distribution
        for idx, percentage in enumerate(distributions):
            if idx >= self.winner_count:
                break
            random_ticket = tickets.order_by("?").first()
            if random_ticket and all(w.ticket != random_ticket for w in winners):
                new_winner = Winner.objects.create(
                    character=random_ticket.character,
                    ticket=random_ticket,
                    prize_amount=self.total_pot * (percentage / 100.0),
                )
                winners.append(new_winner)

                profile, _ = UserProfile.objects.get_or_create(user=random_ticket.user)
                profile.points += int(new_winner.prize_amount / 1000)
                profile.save()
                profile.check_rewards()
        return winners