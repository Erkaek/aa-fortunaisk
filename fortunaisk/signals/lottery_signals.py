# fortunaisk/signals/lottery_signals.py
import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from fortunaisk.notifications import send_discord_notification
from fortunaisk.models import Lottery, Winner, UserProfile

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Lottery)
def notify_discord_on_lottery_creation(sender, instance: Lottery, created: bool, **kwargs) -> None:
    if created:
        embed = {
            "title": "New Lottery Created!",
            "color": 3066993,  # green color
            "fields": [
                {"name": "Reference", "value": instance.lottery_reference, "inline": False},
                {"name": "Ticket Price", "value": f"{instance.ticket_price} ISK", "inline": False},
                {
                    "name": "End Date",
                    "value": instance.end_date.strftime("%Y-%m-%d %H:%M:%S"),
                    "inline": False,
                },
                {
                    "name": "Payment Receiver",
                    "value": str(instance.payment_receiver),
                    "inline": False,
                },
            ],
        }
        instance.notify_discord(embed)


@receiver(pre_delete, sender=Lottery)
def notify_discord_on_lottery_deletion(sender, instance: Lottery, **kwargs) -> None:
    embed = {
        "title": "Lottery Deleted!",
        "color": 15158332,  # red color
        "fields": [
            {"name": "Reference", "value": instance.lottery_reference, "inline": False},
            {"name": "Status", "value": "Deleted", "inline": False},
        ],
    }
    instance.notify_discord(embed)


@receiver(post_save, sender=Winner)
def award_points_to_winners(sender, instance: Winner, created: bool, **kwargs) -> None:
    if created:
        profile, _ = UserProfile.objects.get_or_create(user=instance.ticket.user)
        # example: 100 points for each winner
        profile.points += 100
        profile.save()
        profile.check_rewards()
        send_discord_notification(
            message=f"Congratulations {instance.ticket.user.username}, you earned 100 points for winning!"
        )
