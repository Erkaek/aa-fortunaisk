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


@receiver(post_save, sender=Lottery)
def lottery_post_save(sender, instance, created, **kwargs):
    """
    After saving a Lottery, compare the old status to the new one
    and send Discord notifications if necessary.
    """
    if created:
        # Notification of creation
        try:
            corp_name = (
                instance.payment_receiver.corporation_name
                if instance.payment_receiver
                else "Unknown Corporation"
            )
        except EveCorporationInfo.DoesNotExist:
            corp_name = "Unknown Corporation"

        embed = {
            "title": "✨ **New Lottery Created!** ✨",
            "color": 3066993,  # Green color
            "fields": [
                {
                    "name": "📌 **Reference**",
                    "value": instance.lottery_reference,
                    "inline": False,
                },
                {
                    "name": "💰 **Ticket Price**",
                    "value": f"{instance.ticket_price} ISK",
                    "inline": False,
                },
                {
                    "name": "📅 **End Date**",
                    "value": instance.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": False,
                },
                {
                    "name": "🔑 **Payment Receiver**",
                    "value": corp_name,
                    "inline": False,
                },
            ],
            "footer": {
                "text": "Good luck to everyone! 🍀",
                "icon_url": "https://i.imgur.com/4M34hi2.png",
            },
            "timestamp": instance.start_date.isoformat(),
        }
        logger.debug(f"Sending creation embed: {embed}")
        send_discord_notification(embed=embed)

    else:
        old_status = getattr(instance, "_old_status", None)
        if old_status and old_status != instance.status:
            if instance.status == "completed":
                # Check if there are winners - handled via Winner signals
                # If no winners, send a notification
                winners_exist = instance.winners.exists()
                if not winners_exist:
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
                            f"The lottery **{instance.lottery_reference}** has ended without any winners. 😞"
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
                # Lottery cancelled
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
