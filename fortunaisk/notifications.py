# fortunaisk/notifications.py

# Standard Library
import logging
from datetime import datetime

# Third Party
import requests

# Django
from django.core.cache import cache
from django.db.models import QuerySet

# Alliance Auth
from allianceauth.notifications import notify as alliance_notify

# Discord service
try:
    # Alliance Auth
    from allianceauth.services.modules.discord import DiscordBotService

    discord_service = DiscordBotService()
    logging.getLogger(__name__).info(
        "[DiscordService] initialized, enabled=%s", discord_service.enabled
    )
except ImportError:
    discord_service = None
    logging.getLogger(__name__).warning("[DiscordService] not available (ImportError)")

# fortunaisk
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)

LEVEL_COLORS = {
    "info": 0x3498DB,
    "success": 0x2ECC71,
    "warning": 0xF1C40F,
    "error": 0xE74C3C,
}


def build_embed(
    title: str, description: str = None, fields: list[dict] = None, level: str = "info"
) -> dict:
    """
    Build a Discord embed payload with timestamp, color, optional description and fields.
    """
    embed = {
        "title": title,
        "color": LEVEL_COLORS.get(level, LEVEL_COLORS["info"]),
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": "Good luck to all participants! 🍀"},
    }
    if description:
        embed["description"] = description
    if fields:
        embed["fields"] = fields

    logger.debug(
        "[build_embed] title=%r, description=%r, fields=%r, level=%r → embed=%r",
        title,
        description,
        fields,
        level,
        embed,
    )
    return embed


def get_webhook_url() -> str:
    """
    Retrieve and cache the Discord webhook URL for public announcements.
    """
    url = cache.get("discord_webhook_url")
    if url is None:
        cfg = WebhookConfiguration.objects.first()
        url = cfg.webhook_url if cfg and cfg.webhook_url else ""
        cache.set("discord_webhook_url", url or "", 300)
        logger.debug("[get_webhook_url] fetched from DB and cached: %r", url)
    else:
        logger.debug("[get_webhook_url] fetched from cache: %r", url)
    return url


def send_webhook_notification(embed: dict = None, content: str = None) -> bool:
    """
    Send an embed or plain content via the public Discord webhook.
    Returns True on HTTP 2xx, False otherwise.
    """
    url = get_webhook_url()
    if not url:
        logger.warning("[send_webhook] no webhook URL, skipping")
        return False

    payload = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content

    logger.debug("[send_webhook] POST %s payload=%r", url, payload)
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("[send_webhook] status=%s OK", resp.status_code)
        return True
    except Exception as e:
        # .text may contain Discord error description
        body = getattr(e, "response", None) and e.response.text or ""
        logger.error(
            "[send_webhook] failed status=%s, error=%s, body=%r",
            getattr(e, "response", None) and e.response.status_code,
            e,
            body,
            exc_info=True,
        )
        return False


def send_discord_dm(user, embed: dict = None, content: str = None) -> bool:
    """
    Attempt to send a private Discord DM via AllianceAuth's Discord service.
    Returns True if queued, False otherwise.
    """
    if discord_service is None:
        logger.warning(
            "[send_dm] Discord service unavailable (None) for %s", user.username
        )
        return False
    if not discord_service.enabled:
        logger.warning("[send_dm] Discord service disabled for %s", user.username)
        return False

    logger.debug(
        "[send_dm] preparing DM to %s; embed=%r, content=%r",
        user.username,
        embed,
        content,
    )
    try:
        discord_service.send_message(user=user, embed=embed, message=content or "")
        logger.info("[send_dm] queued DM to %s", user.username)
        return True
    except Exception as e:
        logger.error("[send_dm] exception for %s: %s", user.username, e, exc_info=True)
        return False


def notify_discord_or_fallback(
    users,
    *,
    title: str = None,
    message: str = None,
    embed: dict = None,
    level: str = "info",
    private: bool = False,
):
    """
    Notify one or more users.
    - private=True: DM first, then fallback
    - else: webhook first, then fallback per-user
    """
    if embed is None and title:
        embed = build_embed(title=title, description=message, level=level)
        message = None

    if isinstance(users, QuerySet):
        recipients = list(users)
    elif isinstance(users, (list, tuple)):
        recipients = users
    else:
        recipients = [users]

    logger.debug(
        "[notify] private=%s recipients=%s title=%r message=%r embed=%r",
        private,
        [u.username for u in recipients],
        title,
        message,
        embed,
    )

    def flatten(e: dict) -> str:
        text = e.get("description", "") or ""
        if not text and e.get("fields"):
            text = "\n".join(f"{f['name']}: {f['value']}" for f in e["fields"])
        return text

    # PRIVATE flow
    if private:
        for user in recipients:
            ok = send_discord_dm(user=user, embed=embed, content=message)
            if not ok:
                fallback = message or (embed and flatten(embed)) or ""
                logger.info(
                    "[notify][fallback] DM failed for %s, AllianceAuth → %r",
                    user.username,
                    fallback,
                )
                alliance_notify(
                    user=user,
                    title=title or (embed.get("title") if embed else "Notification"),
                    message=fallback,
                    level=level,
                )
        return

    # PUBLIC flow via webhook
    if embed or message:
        if send_webhook_notification(embed=embed, content=message):
            logger.debug("[notify] public webhook succeeded, done")
            return
        logger.warning("[notify] public webhook failed, falling back per-user")

    fb = message or ""
    if embed and not message:
        fb = flatten(embed)

    for user in recipients:
        logger.debug(
            "[notify][fallback] sending AllianceAuth to %s → %r", user.username, fb
        )
        try:
            alliance_notify(
                user=user,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fb,
                level=level,
            )
            logger.info("[notify][fallback] AllianceAuth sent to %s", user.username)
        except Exception as e:
            logger.error(
                "[notify][fallback] AllianceAuth failed for %s: %s",
                user.username,
                e,
                exc_info=True,
            )


def notify_alliance(user, title: str, message: str, level: str = "info"):
    logger.debug(
        "[notify_alliance] user=%s title=%r message=%r", user.username, title, message
    )
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info("[notify_alliance] sent to %s", user.username)
    except Exception as e:
        logger.error(
            "[notify_alliance] failed for %s: %s", user.username, e, exc_info=True
        )
