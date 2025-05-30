# fortunaisk/models/webhook.py

# Standard Library
import logging

# Django
from django.contrib.auth import get_user_model
from django.db import models

logger = logging.getLogger(__name__)


class WebhookConfiguration(models.Model):
    """
    Stores a single Discord webhook URL along with what events it should fire on
    and optional role pings.
    """

    # A short internal name to distinguish multiple webhook configurations.
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Configuration Name",
        help_text="A unique name for this webhook configuration.",
        blank=True,
        default="",
    )

    webhook_url = models.URLField(
        verbose_name="Discord Webhook URL",
        help_text="The URL to post embeds and messages to.",
        blank=True,
        null=True,
    )
    # list of event keys this config should handle, e.g. ["lottery_created", "anomaly_detected"]
    notification_config = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Events to Notify",
        help_text="Which events (by key) should be sent to this webhook.",
    )
    # optional list of Discord role IDs to @mention
    ping_roles = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Ping Roles",
        help_text="List of Discord role IDs to mention when sending.",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    created_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="webhook_configurations",
        verbose_name="Created By",
    )

    class Meta:
        default_permissions = ()

    def __str__(self):
        display = self.name or f"Webhook #{self.pk}"
        return f"{display} → {self.webhook_url or 'No URL set'}"
