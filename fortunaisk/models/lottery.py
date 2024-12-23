# fortunaisk/models/lottery.py

# Standard Library
import random
import string
from datetime import timedelta  # Assurez-vous que cette importation est en place

# Django
from django.db import models

# fortunaisk
from fortunaisk.models.ticket import TicketPurchase, Winner


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
            ("admin_dashboard", "Can access admin dashboard"),  # Ajout de la permission
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
        Ensure the winners_distribution is valid.
        """
        if self.winners_distribution:
            if len(self.winners_distribution) != self.winner_count:
                raise ValueError(
                    "Mismatch between winners_distribution and winner_count."
                )
            if round(sum(self.winners_distribution), 2) != 100.0:
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

    def complete_lottery(self):
        if self.status != "active":
            return

        self.status = "completed"
        winners = self.select_winners()
        self.notify_discord(winners)
        self.save()

    def select_winners(self):
        tickets = TicketPurchase.objects.filter(lottery=self)
        if not tickets.exists():
            return []

        winners = []
        selected_ticket_ids = set()
        for idx, percentage in enumerate(self.winners_distribution):
            if idx >= self.winner_count:
                break
            # Ensure unique winners
            available_tickets = tickets.exclude(id__in=selected_ticket_ids)
            if not available_tickets.exists():
                break
            random_ticket = available_tickets.order_by("?").first()
            if random_ticket:
                selected_ticket_ids.add(random_ticket.id)
                prize_amount = self.total_pot * (percentage / 100.0)
                winner = Winner.objects.create(
                    character=random_ticket.character,
                    ticket=random_ticket,
                    prize_amount=prize_amount,
                )
                winners.append(winner)

        return winners

    def notify_discord(self, winners):
    # fortunaisk
    from fortunaisk.notifications import send_discord_notification
    
    if not winners:
        message = f"⚠️ La loterie {self.lottery_reference} s'est terminée sans gagnant."
        send_discord_notification(message=message)
        return

    for winner in winners:
        embed = {
            "title": "🎉🎉 **Félicitations au Gagnant!** 🎉🎉",
            "description": f"Nous sommes ravis d'annoncer que **{winner.character.character_name}** a remporté la loterie **{self.lottery_reference}** !",
            "color": 0xFFD700,  # Or
            "thumbnail": {
                "url": "https://i.imgur.com/4M34hi2.png"  # Image de trophée
            },
            "fields": [
                {
                    "name": "🏆 **Utilisateur**",
                    "value": f"{winner.ticket.user.username}",
                    "inline": True
                },
                {
                    "name": "🛡️ **Personnage**",
                    "value": f"{winner.character.character_name}",
                    "inline": True
                },
                {
                    "name": "💰 **Prix**",
                    "value": f"{winner.prize_amount:,.2f} ISK",
                    "inline": True
                },
                {
                    "name": "📅 **Date de Gain**",
                    "value": f"{winner.won_at.strftime('%Y-%m-%d %H:%M')}",
                    "inline": False
                }
            ],
            "footer": {
                "text": "Bonne chance à tous! 🍀",
                "icon_url": "https://i.imgur.com/4M34hi2.png"  # Icône du footer
            },
            "timestamp": winner.won_at.isoformat()
        }
        send_discord_notification(embed=embed)

    @property
    def participant_count(self):
        """Returns the number of participants in the lottery."""
        return self.ticket_purchases.count()
