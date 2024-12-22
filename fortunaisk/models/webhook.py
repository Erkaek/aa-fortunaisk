# fortunaisk/models/webhook.py

import logging
from django.db import models

logger = logging.getLogger(__name__)


class WebhookConfiguration(models.Model):
    """
    Stores the Discord webhook URL for sending notifications.
    """

    webhook_url = models.URLField(
        verbose_name="Discord Webhook URL",
        help_text="The URL for sending Discord notifications",
    )

    def __str__(self) -> str:
        return self.webhook_url
