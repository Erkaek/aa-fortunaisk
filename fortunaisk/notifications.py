# fortunaisk/notifications.py

# Standard Library
import logging
from datetime import datetime

# Third Party
import requests

# Django
from django.db.models import QuerySet

# Alliance Auth
from allianceauth.notifications import notify as alliance_notify

from .models.webhook import WebhookConfiguration

logger = logging.getLogger(__name__)

# Embed colors by level
LEVEL_COLORS = {
    "info": 0x3498DB,
    "success": 0x2ECC71,
    "warning": 0xF1C40F,
    "error": 0xE74C3C,
}


def build_embed(
    title: str,
    description: str | None = None,
    fields: list[dict] | None = None,
    level: str = "info",
    footer: dict | None = None,
) -> dict:
    """
    Build a standard Discord embed payload.

    Creates a properly formatted Discord embed object with consistent styling
    based on the notification level. The embed includes a timestamp and footer.

    Args:
        title (str): The title of the embed
        description (Optional[str]): The main text content of the embed
        fields (Optional[List[dict]]): A list of field objects for structured data
        level (str): The notification level ('info', 'success', 'warning', 'error')
            which determines the color of the embed
        footer (Optional[dict]): Custom footer for the embed, overrides the default

    Returns:
        dict: A dictionary containing the Discord embed object
    """
    embed = {
        "title": title,
        "color": LEVEL_COLORS.get(level, LEVEL_COLORS["info"]),
        "timestamp": datetime.utcnow().isoformat(),
        "footer": footer or {"text": "FortunaISK -- Good luck to all! 🍀"},
    }
    if description:
        embed["description"] = description
    if fields:
        embed["fields"] = fields
    logger.debug("Built embed: %r", embed)
    return embed


def _send_to_webhook(
    cfg: WebhookConfiguration, embed: dict, content: str | None
) -> bool:
    """
    Send a single embed + content (with any role pings) to one webhook config.

    Attempts to post the provided embed and content to the Discord webhook URL
    specified in the configuration. If ping roles are configured, they will be
    mentioned in the message content.

    Args:
        cfg (WebhookConfiguration): The webhook configuration to use
        embed (dict): The Discord embed object to send
        content (Optional[str]): Additional text content to include with the embed

    Returns:
        bool: True if the webhook POST was successful, False otherwise
    """
    url = cfg.webhook_url
    mention = ""
    if cfg.ping_roles:
        mention = " ".join(f"<@&{role_id}>" for role_id in cfg.ping_roles)

    payload = {}
    if mention or content:
        payload["content"] = f"{mention} {content or ''}".strip()
    if embed:
        payload["embeds"] = [embed]

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info(
            "Webhook POST succeeded (cfg=%s, status=%s)", cfg.name, resp.status_code
        )
        return True
    except Exception as exc:
        logger.error("Webhook POST failed (cfg=%s): %s", cfg.name, exc, exc_info=True)
        return False


def notify_discord_or_fallback(
    users,
    *,
    title: str | None = None,
    message: str | None = None,
    embed: dict | None = None,
    level: str = "info",
    private: bool = False,
    event: str | None = None,
):
    """
    Send notifications via Discord webhooks or Alliance Auth notifications.

    This function implements a multi-tiered notification strategy:

    1. If `private=True`: Send direct messages to each user via Alliance Auth.
    2. If `event` is provided: Send to all webhook configurations that have
    subscribed to that event type, including any configured role pings.
    3. If no webhooks succeeded or weren't attempted: Fall back to sending
    individual Alliance Auth notifications to each specified user.

    Args:
        users: A user, list of users, or QuerySet of users to notify
        title: The title of the notification (used for both Discord and AA)
        message: The text content of the notification
        embed: A pre-built Discord embed object (if provided, overrides title/message)
        level: Notification level ('info', 'success', 'warning', 'error')
        private: Whether to only send private notifications
        event: Event type identifier for webhook filtering
    """
    # Build embed if needed
    if embed is None and title:
        embed = build_embed(title=title, description=message, level=level)
        message = None

    # Normalize user list
    if isinstance(users, QuerySet):
        recipient_list = list(users)
    elif isinstance(users, (list, tuple)):
        recipient_list = users
    else:
        recipient_list = [users] if users else []

    # Private path: DM all
    if private:
        text = message or (embed.get("description") if embed else "")
        for u in recipient_list:
            alliance_notify(
                user=u, title=title or embed.get("title", ""), message=text, level=level
            )
            logger.info("Queued private DM for %s: %s", u, title or text)
        return

    # Public path: by event
    public_sent = False
    if event:
        # grab only configs that subscribed to this event
        for cfg in WebhookConfiguration.objects.all():
            if event in (cfg.notification_config or []):
                if _send_to_webhook(cfg, embed, message):
                    public_sent = True

    # If any public webhook succeeded, stop here
    if public_sent:
        return

    # Fallback per-user DM
    fallback_text = message or (embed.get("description") if embed else "")
    for u in recipient_list:
        try:
            alliance_notify(
                user=u,
                title=title or embed.get("title", ""),
                message=fallback_text,
                level=level,
            )
            logger.info("Fallback DM sent to %s: %s", u, fallback_text)
        except Exception as exc:
            logger.error("Fallback notify failed for %s: %s", u, exc, exc_info=True)


def notify_alliance(user, title: str, message: str, level: str = "info"):
    """
    Send a notification via Alliance Auth's internal notification system.

    This function directly uses Alliance Auth's notification system without
    any Discord webhook integration. It's useful for admin-specific notifications
    or when Discord integration is not needed.

    Args:
        user: The user to notify
        title (str): The notification title
        message (str): The notification message content
        level (str): Notification level ('info', 'success', 'warning', 'error')
    """
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info("AllianceAuth notification sent to %s", user)
    except Exception as exc:
        logger.error("AllianceAuth notify failed for %s: %s", user, exc, exc_info=True)
