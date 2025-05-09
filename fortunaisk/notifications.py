# fortunaisk/notifications.py

import logging
import requests
from datetime import datetime
from django.conf import settings
from .models import WebhookConfiguration

logger = logging.getLogger(__name__)

def get_webhook_url():
    cfg = WebhookConfiguration.objects.first()
    if cfg and cfg.webhook_url:
        return cfg.webhook_url
    logger.warning("Discord webhook is not configured.")
    return None

def send_webhook_notification(embed=None, message=None):
    url = get_webhook_url()
    if not url:
        return
    payload = {}
    if embed:
        payload["embeds"] = [embed]
    if message:
        payload["content"] = message
    try:
        resp = requests.post(url, json=payload)
        if resp.status_code not in (200, 204):
            logger.error(f"Webhook error ({resp.status_code}): {resp.text}")
    except Exception as e:
        logger.exception(f"Sending webhook failed: {e}")

def send_discord_dm(discord_user_id, embed=None, content=None):
    """
    Send a DM via your Discord bot; implement with discord.py or similar.
    """
    # TODO: implement actual DM logic here
    pass

def send_ticket_purchase_confirmation_dm(discord_user_id, lottery_ref, quantity, cost, remainder):
    embed = {
        "title": "🎟️ Lottery – Purchase Confirmed!",
        "description": (
            f"You purchased **{quantity}** ticket(s) for **Lottery {lottery_ref}**.\n"
            f"💸 Total cost: **{cost} ISK**" 
            + (f"\n🔄 Overpayment refunded: **{remainder} ISK**" if remainder > 0 else "")
        ),
        "color": 0xFFD700,
        "footer": {"text": f"Good luck with Lottery {lottery_ref}!"},
        "timestamp": datetime.utcnow().isoformat(),
    }
    send_discord_dm(discord_user_id, embed=embed)

def send_ticket_anomaly_dm(discord_user_id, lottery_ref, reason, amount):
    embed = {
        "title": "⚠️ Lottery – Purchase Issue",
        "description": (
            f"Your purchase for **Lottery {lottery_ref}** had an issue:\n"
            f"• **Reason**: {reason}\n"
            f"• **Amount**: {amount} ISK\n\n"
            "❓ Contact an admin if needed."
        ),
        "color": 0xFF4500,
        "footer": {"text": "Purchase not processed"},
        "timestamp": datetime.utcnow().isoformat(),
    }
    send_discord_dm(discord_user_id, embed=embed)

def send_winner_dm(discord_user_id, lottery_ref, prize_amount, ticket_id):
    embed = {
        "title": "🏆 Lottery – You Won!",
        "description": (
            f"Congratulations! You won **{prize_amount} ISK** in **Lottery {lottery_ref}**.\n"
            f"🎫 Ticket #: **{ticket_id}**"
        ),
        "color": 0x32CD32,
        "footer": {"text": "Thank you for playing!"},
        "timestamp": datetime.utcnow().isoformat(),
    }
    send_discord_dm(discord_user_id, embed=embed)

def create_lottery_created_embed(lottery):
    # Build payout distribution
    if lottery.winners_distribution and lottery.winner_count:
        lines = []
        for idx, pct in enumerate(lottery.winners_distribution, start=1):
            if idx > lottery.winner_count:
                break
            lines.append(f"• **Winner {idx}**: {pct}% of the pot")
        distribution = "\n".join(lines)
    else:
        distribution = "_Not defined_"

    max_tix = str(lottery.max_tickets_per_user) if lottery.max_tickets_per_user else "Unlimited"

    return {
        "title": f"✨ New Lottery **#{lottery.lottery_reference}** Launched!",
        "description": (
            f"📅 **Ends**: {lottery.end_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"💰 **Ticket Price**: {lottery.ticket_price} ISK\n"
            f"🎟️ **Max Tickets/User**: {max_tix}\n\n"
            f"📊 **Payout Distribution:**\n{distribution}"
        ),
        "color": 0x00BFFF,
        "footer": {"text": "Participate now before it closes! 🍀"},
        "timestamp": lottery.start_date.isoformat(),
    }

def create_lottery_completed_with_winners_embed(lottery, winners):
    lines = [
        f"• <@{w.ticket.user.discord_id}> — **{w.prize_amount} ISK** (ticket #{w.ticket.id})"
        for w in winners
    ]
    return {
        "title": f"🏆 Lottery **#{lottery.lottery_reference}** Completed!",
        "description": (
            f"💰 **Total Pot**: {lottery.total_pot} ISK\n"
            f"📅 **Ended**: {lottery.end_date.strftime('%Y-%m-%d %H:%M')}\n\n"
            + "\n".join(lines)
        ),
        "color": 0xFFD700,
        "footer": {"text": "Congratulations to the winners! 🎉"},
        "timestamp": lottery.end_date.isoformat(),
    }

def create_lottery_completed_no_winner_embed(lottery):
    return {
        "title": f"🏆 Lottery **#{lottery.lottery_reference}** Completed!",
        "description": (
            f"💰 **Total Pot**: {lottery.total_pot} ISK\n"
            f"📅 **Ended**: {lottery.end_date.strftime('%Y-%m-%d %H:%M')}\n\n"
            "_No winners were drawn._"
        ),
        "color": 0xFF4500,
        "footer": {"text": "Better luck next time! 🍀"},
        "timestamp": lottery.end_date.isoformat(),
    }

def create_lottery_cancelled_embed(lottery):
    return {
        "title": f"🚫 Lottery **#{lottery.lottery_reference}** Cancelled",
        "description": (
            f"This lottery was cancelled on {lottery.end_date.strftime('%Y-%m-%d %H:%M')}."
        ),
        "color": 0xA9A9A9,
        "footer": {"text": "Contact an admin for details."},
        "timestamp": datetime.utcnow().isoformat(),
    }
