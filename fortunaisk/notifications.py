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
# Try to import the Discord service under both possible names,
# then log exactly what we got and whether it's enabled.
discord_service = None
discord_class_name = None

try:
    mod = importlib.import_module("allianceauth.services.modules.discord")
    for candidate in ("DiscordService", "DiscordBotService"):
        cls = getattr(mod, candidate, None)
        if cls:
            discord_service = cls()
            discord_class_name = candidate
            break
    if discord_service:
        logger.info(
            "[DiscordService] loaded class=%s enabled=%s",
            discord_class_name,
            getattr(discord_service, "enabled", "<no-enabled-attr>"),
        )
    else:
        logger.warning(
            "[DiscordService] module found but no DiscordService/DiscordBotService class"
        )
except ImportError:
    logger.warning("[DiscordService] module not installed or not in INSTALLED_APPS")

# -------------------------------------------------------------------

# Discord embed colors
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

    logger.debug(
        "[build_embed] title=%r description=%r fields=%r level=%r → %r",
        title,
        description,
        fields,
        level,
        embed,
    )
    return embed


def get_webhook_url() -> str:
    url = cache.get("discord_webhook_url")
    if url is None:
        cfg = WebhookConfiguration.objects.first()
        url = cfg.webhook_url if cfg and cfg.webhook_url else ""
        cache.set("discord_webhook_url", url or "", 300)
        logger.debug("[get_webhook_url] fetched from DB: %r", url)
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

    logger.debug("[send_webhook] POST %s payload=%r", url, payload)
    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        logger.info("[send_webhook] status=%s OK", resp.status_code)
        return True
    except Exception as e:
        status = getattr(e, "response", None) and e.response.status_code
        body = getattr(e, "response", None) and e.response.text
        logger.error(
            "[send_webhook] failed status=%s error=%s body=%r",
            status,
            e,
            body,
            exc_info=True,
        )
        return False


def send_discord_dm(user, embed: dict = None, content: str = None) -> bool:
    if discord_service is None:
        logger.warning("[send_dm] Discord service is None; cannot DM %s", user.username)
        return False
    if not getattr(discord_service, "enabled", False):
        logger.warning(
            "[send_dm] Discord service '%s' disabled; cannot DM %s",
            discord_class_name,
            user.username,
        )
        return False

    logger.debug(
        "[send_dm] sending via %s to %s embed=%r content=%r",
        discord_class_name,
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

    # public
    if embed or message:
        if send_webhook_notification(embed=embed, content=message):
            logger.debug("[notify] public webhook succeeded")
            return
        logger.warning("[notify] public webhook failed, fallback per-user")

    fallback = message or ""
    if embed and not message:
        fallback = flatten(embed)

    for user in recipients:
        logger.debug(
            "[notify][fallback] AllianceAuth → %s : %r", user.username, fallback
        )
        try:
            alliance_notify(
                user=user,
                title=title or (embed.get("title") if embed else "Notification"),
                message=fallback,
                level=level,
            )
            logger.info("[notify][fallback] sent to %s", user.username)
        except Exception as e:
            logger.error(
                "[notify][fallback] error for %s: %s", user.username, e, exc_info=True
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
            "[notify_alliance] error for %s: %s", user.username, e, exc_info=True
        )
