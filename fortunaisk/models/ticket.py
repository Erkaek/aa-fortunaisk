# fortunaisk/models/ticket.py

# Standard Library
from decimal import Decimal

# Django
from django.contrib.auth import get_user_model
from django.db import models

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter

User = get_user_model()


class TicketPurchase(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processed", "Processed"),
        ("failed", "Failed"),
    ]

    lottery = models.ForeignKey(
        "fortunaisk.Lottery",
        on_delete=models.CASCADE,
        related_name="ticket_purchases",
        verbose_name="Lottery",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ticket_purchases",
        verbose_name="Django User",
    )
    character = models.ForeignKey(
        EveCharacter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_purchases",
        verbose_name="Eve Character",
        help_text="Eve character that made the payment (if identifiable).",
    )
    amount = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Ticket Amount",
        help_text="Amount of ISK paid for this ticket.",
    )
    purchase_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Purchase Date"
    )
    payment_id = models.CharField(
        max_length=255, null=True, blank=True, verbose_name="Payment ID", unique=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        verbose_name="Ticket Status",
    )

    def __str__(self) -> str:
        return (
            f"TicketPurchase(user={self.user.username}, "
            f"lottery={self.lottery.lottery_reference}, "
            f"amount={self.amount}, status={self.status})"
        )


class Winner(models.Model):
    ticket = models.ForeignKey(
        TicketPurchase,
        on_delete=models.CASCADE,
        related_name="winners",
        verbose_name="Ticket Purchase",
    )
    character = models.ForeignKey(
        EveCharacter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="winners",
        verbose_name="Winning Eve Character",
    )
    prize_amount = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Prize Amount",
        help_text="ISK amount that the winner receives.",
    )
    won_at = models.DateTimeField(auto_now_add=True, verbose_name="Winning Date")
    distributed = models.BooleanField(
        default=False,
        verbose_name="Prize Distributed",
        help_text="Indicates whether the prize has been distributed to the winner.",
    )

    def __str__(self) -> str:
        char_name = self.character.character_name if self.character else "Unknown"
        return f"Winner for {self.ticket.lottery.lottery_reference}: {char_name}"


class TicketAnomaly(models.Model):
    lottery = models.ForeignKey(
        "fortunaisk.Lottery",
        on_delete=models.CASCADE,
        related_name="anomalies",
        verbose_name="Lottery",
        null=True,
        blank=True,
    )
    character = models.ForeignKey(
        EveCharacter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Eve Character",
    )
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Django User",
    )
    reason = models.TextField(verbose_name="Anomaly Reason")
    payment_date = models.DateTimeField(verbose_name="Payment Date")
    amount = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="Anomaly Amount",
    )
    payment_id = models.CharField(max_length=255, verbose_name="Payment ID")
    recorded_at = models.DateTimeField(auto_now_add=True, verbose_name="Recorded At")

    def __str__(self) -> str:
        if self.lottery:
            return f"Anomaly: {self.reason} (Lottery {self.lottery.lottery_reference})"
        return f"Anomaly: {self.reason} (No Lottery)"
