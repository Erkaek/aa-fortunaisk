# fortunaisk/signals/webhook_signals.py

# Standard Library
import logging

# Django
from django.core.cache import cache  # type: ignore
from django.db.models.signals import post_delete, post_save  # type: ignore
from django.dispatch import receiver  # type: ignore

# fortunaisk
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)


@receiver(post_save, sender=WebhookConfiguration)
def clear_webhook_cache_on_save(sender, instance, **kwargs):
    cache.delete("discord_webhook_url")
    logger.info(
        "Cache 'discord_webhook_url' invalidé suite à la mise à jour du webhook."
    )


@receiver(post_delete, sender=WebhookConfiguration)
def clear_webhook_cache_on_delete(sender, instance, **kwargs):
    cache.delete("discord_webhook_url")
    logger.info(
        "Cache 'discord_webhook_url' invalidé suite à la suppression du webhook."
    )
