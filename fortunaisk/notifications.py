# fortunaisk/notifications.py

# Standard Library
import logging

# Third Party
import requests

logger = logging.getLogger(__name__)


def send_discord_webhook(embed):
    try:
        from .models import WebhookConfiguration

        webhook_config = WebhookConfiguration.objects.first()
        if not webhook_config:
            logger.warning("Aucun webhook configuré.")
            return

        webhook_url = webhook_config.webhook_url
        data = {"embeds": [embed]}

        response = requests.post(webhook_url, json=data)
        if response.status_code != 204:
            logger.error(
                f"Échec de l’envoi du message (Code {response.status_code}): {response.text}"
            )
    except Exception as e:
        logger.exception("Erreur lors de l'envoi d'une notification Discord: %s", e)


def send_discord_notification(webhook_url, message):
    payload = {"content": message}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Discord notification: {e}")
