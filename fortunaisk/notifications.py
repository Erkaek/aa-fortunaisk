# fortunaisk/notifications.py
# Standard Library
import logging

# Third Party
import requests

# Django
from django.core.cache import cache

# fortunaisk
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)


def get_webhook_url() -> str:
    """
    Retrieves the Discord webhook URL from the singleton configuration, cached for 5 minutes.
    """
    webhook_url = cache.get("discord_webhook_url")
    if webhook_url is None:
        webhook_config = WebhookConfiguration.get_solo()
        if webhook_config and webhook_config.webhook_url:
            webhook_url = webhook_config.webhook_url
            cache.set("discord_webhook_url", webhook_url, 300)
        else:
            logger.warning("No webhook configured.")
            webhook_url = ""
    return webhook_url


def send_discord_notification(embed=None, message: str = None) -> None:
    """
    Sends a notification to Discord via the configured webhook.
    """
    try:
        webhook_url = get_webhook_url()
        if not webhook_url:
            return

        data = {}
        if embed:
            data["embeds"] = [embed]
        if message:
            data["content"] = message

        response = requests.post(webhook_url, json=data)
        if response.status_code not in (200, 204):
            logger.error(
                f"Failed to send Discord message (HTTP {response.status_code}): {response.text}"
            )
    except Exception as e:
        logger.exception(f"Error sending Discord notification: {e}")
