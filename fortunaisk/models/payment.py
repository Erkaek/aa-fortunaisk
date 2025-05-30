# fortunaisk/models/payment.py

# Standard Library
from decimal import Decimal

# Django
from django.contrib.auth import get_user_model
from django.db import models

# Alliance Auth
from allianceauth.eveonline.models import EveCharacter


class ProcessedPayment(models.Model):
    payment_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Payment ID",
        help_text="Unique identifier for processed payments.",
    )
    character = models.ForeignKey(
        EveCharacter,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Eve Character",
        help_text="EVE character (if identified).",
    )
    user = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Django User",
        help_text="Django user (if identified).",
    )
    amount = models.DecimalField(
        max_digits=25,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total Paid Amount",
        help_text="Total amount paid in ISK.",
    )
    payed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Paid At",
        help_text="Payment date & time.",
    )
    processed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Processed At",
        help_text="Timestamp when the payment was processed.",
    )

    class Meta:
        default_permissions = ()

    def __str__(self):
        return f"ProcessedPayment(payment_id={self.payment_id})"
