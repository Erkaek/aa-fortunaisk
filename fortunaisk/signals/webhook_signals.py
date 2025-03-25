"""
Signals for handling WebhookConfiguration model events.

When a WebhookConfiguration instance is saved or deleted, this clears the
'discord_webhook_url' cache to ensure the latest webhook URL is used.
"""

# fortunaisk/signals/webhook_signals.py

# Standard Library
import logging

# Django
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)


@receiver(post_save, sender=WebhookConfiguration)
def clear_webhook_cache_on_save(sender, instance, **kwargs):
    cache.delete("discord_webhook_url")
    logger.info("Cache 'discord_webhook_url' invalidated due to webhook update.")


@receiver(post_delete, sender=WebhookConfiguration)
def clear_webhook_cache_on_delete(sender, instance, **kwargs):
    cache.delete("discord_webhook_url")
    logger.info("Cache 'discord_webhook_url' invalidated due to webhook deletion.")
