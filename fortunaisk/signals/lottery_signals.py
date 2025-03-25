# fortunaisk/signals/lottery_signals.py

# Standard Library
import logging

# Django
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import Lottery
from fortunaisk.notifications import send_discord_notification

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Lottery)
def lottery_pre_save(sender, instance, **kwargs):
    """
    Before saving a Lottery, retrieve the old status for comparison.
    """
    if instance.pk:
        try:
            old_instance = Lottery.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Lottery.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


def create_winners_embed(lottery, winners):
    """
    Create a Discord embed for the winners of a lottery.
    """
    winner_list = []
    for winner in winners:
        username = winner.ticket.user.username if winner.ticket.user else "Unknown User"
        character_name = (
            winner.character.character_name if winner.character else "Unknown Character"
        )
        prize_amount = f"{winner.prize_amount} ISK"
        winner_list.append(
            f"• **{username}** with character **{character_name}** won **{prize_amount}**."
        )

    winners_str = "\n".join(winner_list) if winner_list else "No winners."

    embed = {
        "title": "🏆 **Lottery Completed!** 🏆",
        "description": f"The lottery **{lottery.lottery_reference}** has concluded. Here are the winners:",
        "color": 15844367,  # Orange color
        "fields": [
            {
                "name": "📌 **Reference**",
                "value": lottery.lottery_reference,
                "inline": False,
            },
            {
                "name": "💰 **Total Pot**",
                "value": f"{lottery.total_pot} ISK",
                "inline": False,
            },
            {
                "name": "📅 **End Date**",
                "value": lottery.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "inline": False,
            },
            {
                "name": "🔑 **Payment Receiver**",
                "value": (
                    lottery.payment_receiver.corporation_name
                    if lottery.payment_receiver
                    else "Unknown Corporation"
                ),
                "inline": False,
            },
            {
                "name": "🎖️ **Winners**",
                "value": winners_str,
                "inline": False,
            },
        ],
        "footer": {
            "text": "Congratulations to all winners! 🎉",
            "icon_url": "https://i.imgur.com/4M34hi2.png",
        },
        "timestamp": lottery.end_date.isoformat(),
    }

    return embed


def create_creation_embed(lottery):
    """
    Create a Discord embed for the creation of a new lottery.
    """
    try:
        corp_name = (
            lottery.payment_receiver.corporation_name
            if lottery.payment_receiver
            else "Unknown Corporation"
        )
    except EveCorporationInfo.DoesNotExist:
        corp_name = "Unknown Corporation"

    # Format the prize distribution
    if lottery.winners_distribution and lottery.winner_count:
        distribution_lines = []
        for idx, percentage in enumerate(lottery.winners_distribution, start=1):
            distribution_lines.append(f"• **Winner {idx}**: {percentage}%")
        distribution_str = "\n".join(distribution_lines)
    else:
        distribution_str = "No distribution defined."

    # Déterminer le nombre maximal de tickets par utilisateur
    if lottery.max_tickets_per_user is not None:
        max_tickets = str(lottery.max_tickets_per_user)
    else:
        max_tickets = "Illimité"

    embed = {
        "title": "✨ **New Lottery Created!** ✨",
        "color": 3066993,  # Green color
        "fields": [
            {
                "name": "📌 **Reference**",
                "value": lottery.lottery_reference,
                "inline": False,
            },
            {
                "name": "📅 **End Date**",
                "value": lottery.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "inline": False,
            },
            {
                "name": "💰 **Ticket Price**",
                "value": f"{lottery.ticket_price} ISK",
                "inline": False,
            },
            {
                "name": "🎟️ **Max Tickets Per User**",
                "value": max_tickets,
                "inline": False,
            },
            {
                "name": "🔑 **Payment Receiver**",
                "value": corp_name,
                "inline": False,
            },
            {
                "name": "🏆 **Number of Winners**",
                "value": f"{lottery.winner_count}",
                "inline": False,
            },
            {
                "name": "📊 **Prize Distribution**",
                "value": distribution_str,
                "inline": False,
            },
        ],
        "footer": {
            "text": "Good luck to everyone! 🍀",
            "icon_url": "https://i.imgur.com/4M34hi2.png",
        },
        "timestamp": lottery.start_date.isoformat(),
    }

    return embed


@receiver(post_save, sender=Lottery)
def lottery_post_save(sender, instance, created, **kwargs):
    """
    After saving a Lottery, compare the old status to the new one
    and send Discord notifications if necessary.
    """
    if created:
        # Notification of creation
        embed = create_creation_embed(instance)
        logger.debug(f"Sending creation embed: {embed}")
        send_discord_notification(embed=embed)

    else:
        old_status = getattr(instance, "_old_status", None)
        if old_status and old_status != instance.status:
            if instance.status == "completed":
                # Check if there are winners
                winners_exist = instance.winners.exists()
                if winners_exist:
                    # Retrieve all winners
                    winners = instance.winners.select_related(
                        "ticket__user", "character"
                    ).all()
                    embed = create_winners_embed(instance, winners)
                    logger.debug(f"Sending winners embed: {embed}")
                    send_discord_notification(embed=embed)
                else:
                    # Notification of completion without winners
                    try:
                        corp_name = (
                            instance.payment_receiver.corporation_name
                            if instance.payment_receiver
                            else "Unknown Corporation"
                        )
                    except EveCorporationInfo.DoesNotExist:
                        corp_name = "Unknown Corporation"

                    embed = {
                        "title": "🎉 **Lottery Completed Without Winners** 🎉",
                        "description": (
                            f"The lottery **{instance.lottery_reference}** has concluded without any winners. 😞"
                        ),
                        "color": 0xFF0000,  # Red color
                        "fields": [
                            {
                                "name": "📌 **Reference**",
                                "value": instance.lottery_reference,
                                "inline": False,
                            },
                            {
                                "name": "💰 **Total Pot**",
                                "value": f"{instance.total_pot} ISK",
                                "inline": False,
                            },
                            {
                                "name": "📅 **End Date**",
                                "value": instance.end_date.strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                ),
                                "inline": False,
                            },
                            {
                                "name": "🔑 **Payment Receiver**",
                                "value": corp_name,
                                "inline": False,
                            },
                        ],
                        "footer": {
                            "text": "Better luck next time! 🍀",
                            "icon_url": "https://i.imgur.com/4M34hi2.png",
                        },
                        "timestamp": instance.end_date.isoformat(),
                    }
                    logger.debug(f"Sending completion without winners embed: {embed}")
                    send_discord_notification(embed=embed)

            elif instance.status == "cancelled":
                # Notification of cancellation
                try:
                    corp_name = (
                        instance.payment_receiver.corporation_name
                        if instance.payment_receiver
                        else "Unknown Corporation"
                    )
                except EveCorporationInfo.DoesNotExist:
                    corp_name = "Unknown Corporation"

                embed = {
                    "title": "🚫 **Lottery Cancelled** 🚫",
                    "description": (
                        f"The lottery **{instance.lottery_reference}** has been cancelled. 🛑"
                    ),
                    "color": 0xFF0000,  # Red color
                    "fields": [
                        {
                            "name": "📌 **Reference**",
                            "value": instance.lottery_reference,
                            "inline": False,
                        },
                        {
                            "name": "🔄 **Status**",
                            "value": "Cancelled",
                            "inline": False,
                        },
                        {
                            "name": "🔑 **Payment Receiver**",
                            "value": corp_name,
                            "inline": False,
                        },
                    ],
                    "footer": {
                        "text": "Lottery cancelled by the administrator.",
                        "icon_url": "https://i.imgur.com/4M34hi2.png",
                    },
                    "timestamp": instance.end_date.isoformat(),
                }
                logger.debug(f"Sending cancellation embed: {embed}")
                send_discord_notification(embed=embed)

            else:
                # Other status updates
                message = (
                    f"The lottery **{instance.lottery_reference}** has been updated. 📝"
                )
                logger.debug(f"Sending status update message: {message}")
                send_discord_notification(message=message)
