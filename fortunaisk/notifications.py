# fortunaisk/notifications.py

# Standard Library
import logging

# Third Party
import requests

# Django
from django.core.cache import cache

# Alliance Auth
from allianceauth.services.modules.notifications import trigger

# fortunaisk
from fortunaisk.models import WebhookConfiguration  # Assurez-vous que ce modèle existe

logger = logging.getLogger(__name__)


def get_webhook_url() -> str:
    """
    Récupère l'URL du webhook Discord depuis la configuration, avec mise en cache de 5 minutes.
    """
    webhook_url = cache.get("discord_webhook_url")
    if webhook_url is None:
        try:
            webhook_config = WebhookConfiguration.objects.first()
            if webhook_config and webhook_config.webhook_url:
                webhook_url = webhook_config.webhook_url
                cache.set("discord_webhook_url", webhook_url, 300)
            else:
                logger.warning("Aucun webhook configuré.")
                webhook_url = ""
        except Exception as e:
            logger.exception(
                f"Erreur lors de la récupération de la configuration du webhook : {e}"
            )
            webhook_url = ""
    return webhook_url


def send_discord_notification(embed=None, message: str = None) -> None:
    """
    Envoie une notification à Discord via le webhook configuré.
    """
    try:
        webhook_url = get_webhook_url()
        if not webhook_url:
            logger.warning("URL du webhook non configurée. Notification non envoyée.")
            return

        data = {}
        if embed:
            data["embeds"] = [embed]
        if message:
            data["content"] = message

        logger.debug(f"Envoi de la notification Discord avec les données : {data}")

        response = requests.post(webhook_url, json=data)
        if response.status_code not in (200, 204):
            logger.error(
                f"Échec de l'envoi du message Discord (HTTP {response.status_code}) : {response.text}"
            )
        else:
            logger.info("Notification Discord envoyée avec succès.")
    except Exception as e:
        logger.exception(f"Erreur lors de l'envoi de la notification Discord : {e}")


def send_alliance_auth_notification(event_type, user, context):
    """
    Envoie une notification via le système de notification d’Alliance Auth.
    :param event_type: Type d’événement (string)
    :param user: Utilisateur destinataire de la notification
    :param context: Dictionnaire contenant les informations supplémentaires
    """
    try:
        trigger(
            module_name="fortunaisk",
            notification_type=event_type,
            user=user,
            extra=context,
        )
        logger.info(f"Notification '{event_type}' envoyée à {user.username}.")
    except Exception as e:
        logger.exception(
            f"Erreur lors de l'envoi de la notification d'Alliance Auth : {e}"
        )
