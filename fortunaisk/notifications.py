# fortunaisk/notifications.py
"""Module pour les fonctions de notification de FortunaIsk."""

# Standard Library
import logging

# Third Party
import requests

logger = logging.getLogger(__name__)


def send_discord_webhook(embed):
    try:
        from .models import (
            WebhookConfiguration,  # Local import to avoid circular dependency
        )

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
