# fortunaisk/notifications.py

# Standard Library
import logging

# Third Party
import requests

from .webhooks import WebhookConfiguration

logger = logging.getLogger(__name__)


def send_discord_notification(embed=None, message=None):
    """
    Envoie une notification à Discord via le webhook configuré.

    :param embed: Un dictionnaire représentant l'embed Discord.
    :param message: Un message texte simple.
    """
    try:
        webhook_config = WebhookConfiguration.objects.first()
        if not webhook_config:
            logger.warning("Aucun webhook configuré.")
            return

        webhook_url = webhook_config.webhook_url
        data = {}
        if embed:
            data["embeds"] = [embed]
        if message:
            data["content"] = message

        response = requests.post(webhook_url, json=data)
        if response.status_code not in (200, 204):
            logger.error(
                f"Échec de l’envoi du message (Code {response.status_code}): {response.text}"
            )
    except Exception as e:
        logger.exception("Erreur lors de l'envoi d'une notification Discord: %s", e)
