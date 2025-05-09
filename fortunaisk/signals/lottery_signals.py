# fortunaisk/signals/lottery_signals.py

import logging
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from fortunaisk.models import Lottery
from fortunaisk.notifications import (
    send_webhook_notification,
    create_lottery_created_embed,
    create_lottery_completed_with_winners_embed,
    create_lottery_completed_no_winner_embed,
    create_lottery_cancelled_embed,
)

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Lottery)
def lottery_pre_save(sender, instance, **kwargs):
    """
    Store old status on the instance before saving.
    """
    if instance.pk:
        try:
            old = Lottery.objects.get(pk=instance.pk)
            instance._old_status = old.status
        except Lottery.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None

@receiver(post_save, sender=Lottery)
def lottery_post_save(sender, instance, created, **kwargs):
    """
    Send webhook embeds on creation, completion or cancellation.
    """
    if created:
        embed = create_lottery_created_embed(instance)
        send_webhook_notification(embed=embed)
        logger.info(f"Sent 'lottery created' webhook for {instance.lottery_reference}.")
    else:
        old = getattr(instance, "_old_status", None)
        new = instance.status
        if old != new:
            if new == "completed":
                winners = instance.winners.select_related("ticket__user", "character").all()
                if winners:
                    embed = create_lottery_completed_with_winners_embed(instance, winners)
                else:
                    embed = create_lottery_completed_no_winner_embed(instance)
                send_webhook_notification(embed=embed)
                logger.info(f"Sent 'lottery completed' webhook for {instance.lottery_reference}.")
            elif new == "cancelled":
                embed = create_lottery_cancelled_embed(instance)
                send_webhook_notification(embed=embed)
                logger.info(f"Sent 'lottery cancelled' webhook for {instance.lottery_reference}.")
