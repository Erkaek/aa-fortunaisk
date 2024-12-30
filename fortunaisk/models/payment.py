# fortunaisk/models/payment.py

# Django
from django.db import models


class ProcessedPayment(models.Model):
    payment_id = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="Payment ID",
        help_text="Unique identifier for processed payments.",
    )
    processed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Processed At",
        help_text="Timestamp when the payment was processed.",
    )

    class Meta:
        verbose_name = "Processed Payment"
        verbose_name_plural = "Processed Payments"
        default_permissions = ()  # Désactive les permissions automatiques
        permissions = [
            ("user", "User permission"),
            ("admin", "Administrator permission"),
        ]

    def __str__(self):
        return f"ProcessedPayment(payment_id={self.payment_id})"
