# fortunaisk/notifications.py

# Standard Library
import logging

# Third Party
import requests

# Django
from django.conf import settings
from django.core.cache import cache
from django.core.mail import mail_admins

# Alliance Auth
from allianceauth.notifications import notify

from .models import WebhookConfiguration

logger = logging.getLogger(__name__)


def get_webhook_url() -> str:
    webhook_url = cache.get("discord_webhook_url")
    if webhook_url is None:
        try:
            webhook_config = WebhookConfiguration.objects.first()
            if webhook_config and webhook_config.webhook_url:
                webhook_url = webhook_config.webhook_url
                cache.set(
                    "discord_webhook_url", webhook_url, 300
                )  # Cache for 5 minutes
            else:
                logger.warning("No webhook configured.")
                webhook_url = ""
        except Exception as e:
            logger.exception(f"Error retrieving webhook configuration: {e}")
            webhook_url = ""
    return webhook_url


def send_discord_notification(embed=None, message: str = None) -> None:
    try:
        webhook_url = get_webhook_url()
        if not webhook_url:
            logger.warning("Webhook URL is not configured. Notification not sent.")
            return

        data = {}
        if embed:
            data["embeds"] = [embed]
        if message:
            data["content"] = message

        logger.debug(f"Sending Discord notification with data: {data}")

        response = requests.post(webhook_url, json=data)
        if response.status_code not in (200, 204):
            error_msg = f"Failed to send Discord message (HTTP {response.status_code}): {response.text}"
            logger.error(error_msg)
            # Notify admins via email
            if hasattr(settings, "ADMINS") and settings.ADMINS:
                mail_admins(
                    subject="FortunaIsk Discord Notification Failure",
                    message=error_msg,
                    fail_silently=True,
                )
        else:
            logger.info("Discord notification sent successfully.")
    except Exception as e:
        error_msg = f"Error sending Discord notification: {e}"
        logger.exception(error_msg)
        # Notify admins via email
        if hasattr(settings, "ADMINS") and settings.ADMINS:
            mail_admins(
                subject="FortunaIsk Discord Notification Exception",
                message=error_msg,
                fail_silently=True,
            )


def send_alliance_auth_notification(user, title, message, level="info") -> None:
    """
    Sends a notification via Alliance Auth's notification system.
    """
    try:
        notify(user=user, title=title, message=message, level=level)
        logger.info(f"Notification '{title}' sent to {user.username}.")
    except Exception as e:
        error_msg = f"Error sending Alliance Auth notification: {e}"
        logger.exception(error_msg)
        # Notify admins via email
        if hasattr(settings, "ADMINS") and settings.ADMINS:
            mail_admins(
                subject="FortunaIsk Alliance Auth Notification Failure",
                message=error_msg,
                fail_silently=True,
            )
