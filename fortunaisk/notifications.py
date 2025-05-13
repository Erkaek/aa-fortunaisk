# fortunaisk/notifications.py

# Standard Library
import importlib
import logging
from datetime import datetime

# Third Party
import requests

# Django
from django.core.cache import cache
from django.db.models import QuerySet

# Alliance Auth
from allianceauth.notifications import notify as alliance_notify

# fortunaisk
from fortunaisk.models import WebhookConfiguration

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Import DiscordBotService from the correct submodule
discord_service = None
try:
    svc_mod = importlib.import_module("allianceauth.services.modules.discord.service")
    DiscordBotService = getattr(svc_mod, "DiscordBotService", None)
    if DiscordBotService is None:
        raise ImportError("DiscordBotService class not found in service module")
    discord_service = DiscordBotService()
    logger.info(
        "[DiscordService] loaded DiscordBotService, enabled=%s",
        getattr(discord_service, "enabled", False),
    )
except ImportError as e:
    discord_service = None
    logger.warning(f"[DiscordService] could not load DiscordBotService: {e}")

# -------------------------------------------------------------------

LEVEL_COLORS = {
    "info": 0x3498DB,
    "success": 0x2ECC71,
    "warning": 0xF1C40F,
    "error": 0xE74C3C,
}


def build_embed(
    title: str, description: str = None, fields: list[dict] = None, level: str = "info"
) -> dict:
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
    logger.debug("[build_embed] %r", embed)
    return embed


def get_webhook_url() -> str:
    url = cache.get("discord_webhook_url")
    if url is None:
        cfg = WebhookConfiguration.objects.first()
        url = cfg.webhook_url if cfg and cfg.webhook_url else ""
        cache.set("discord_webhook_url", url or "", 300)
        logger.debug("[get_webhook_url] from DB: %r", url)
    else:
        logger.debug("[get_webhook_url] from cache: %r", url)
    return url


def send_webhook_notification(embed: dict = None, content: str = None) -> bool:
    url = get_webhook_url()
    if not url:
        logger.warning("[send_webhook] no webhook URL configured")
        return False

    payload = {}
    if embed:
        payload["embeds"] = [embed]
    if content:
        payload["content"] = content

    logger.debug("[send_webhook] POST %s %r", url, payload)
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("[send_webhook] success status=%s", resp.status_code)
        return True
    except Exception as exc:
        status = getattr(exc, "response", None) and exc.response.status_code
        body = getattr(exc, "response", None) and exc.response.text
        logger.error(
            "[send_webhook] failed status=%s exc=%s body=%r",
            status,
            exc,
            body,
            exc_info=True,
        )
        return False


def send_discord_dm(user, embed: dict = None, content: str = None) -> bool:
    if discord_service is None:
        logger.warning("[send_dm] discord_service is None; cannot DM %s", user.username)
        return False
    if not getattr(discord_service, "enabled", False):
        logger.warning(
            "[send_dm] DiscordBotService disabled; cannot DM %s", user.username
        )
        return False

    logger.debug("[send_dm] to %s embed=%r content=%r", user.username, embed, content)
    try:
        discord_service.send_message(user=user, embed=embed, message=content or "")
        logger.info("[send_dm] queued DM to %s", user.username)
        return True
    except Exception as exc:
        logger.error(
            "[send_dm] exception for %s: %s", user.username, exc, exc_info=True
        )
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
        "[notify] private=%s users=%s title=%r message=%r",
        private,
        [u.username for u in recipients],
        title,
        message,
    )

    def flatten(e: dict) -> str:
        text = e.get("description", "") or ""
        if not text and e.get("fields"):
            text = "\n".join(f"{f['name']}: {f['value']}" for f in e["fields"])
        return text

    if private:
        for user in recipients:
            ok = send_discord_dm(user=user, embed=embed, content=message)
            if not ok:
                fb = message or (embed and flatten(embed)) or ""
                logger.info(
                    "[notify][fallback] DM failed for %s; AllianceAuth → %r",
                    user.username,
                    fb,
                )
                alliance_notify(
                    user=user,
                    title=title or (embed.get("title") if embed else "Notification"),
                    message=fb,
                    level=level,
                )
        return

    # Public path
    if embed or message:
        if send_webhook_notification(embed=embed, content=message):
            return
        logger.warning("[notify] public webhook failed; falling back per-user")

    fb = message or ""
    if embed and not message:
        fb = flatten(embed)

    for user in recipients:
        logger.debug("[notify][fallback] AllianceAuth to %s → %r", user.username, fb)
        try:
            alliance_notify(
                user=user,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fb,
                level=level,
            )
            logger.info("[notify][fallback] sent to %s", user.username)
        except Exception as exc:
            logger.error(
                "[notify][fallback] error for %s: %s", user.username, exc, exc_info=True
            )


def notify_alliance(user, title: str, message: str, level: str = "info"):
    logger.debug(
        "[notify_alliance] user=%s title=%r message=%r", user.username, title, message
    )
    try:
        alliance_notify(user=user, title=title, message=message, level=level)
        logger.info("[notify_alliance] sent to %s", user.username)
    except Exception as exc:
        logger.error(
            "[notify_alliance] error for %s: %s", user.username, exc, exc_info=True
        )
