# fortunaisk/models/webhook.py

# Standard Library
import logging

# Third Party
from solo.models import SingletonModel

# Django
from django.db import models

logger = logging.getLogger(__name__)


class WebhookConfiguration(SingletonModel):
    """
    Stores the Discord webhook URL for sending notifications.
    """

    webhook_url = models.URLField(
        verbose_name="Discord Webhook URL",
        help_text="The URL for sending Discord notifications",
        blank=True,
        null=True,
    )

    def __str__(self) -> str:
        return self.webhook_url or "No Webhook Configured"

    class Meta:
        verbose_name = "Webhook Configuration"
        verbose_name_plural = "Webhook Configuration"
