# fortunaisk/signals/autolottery_signals.py

import json
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from fortunaisk.models import AutoLottery
from fortunaisk.notifications import build_embed, notify_discord_or_fallback

logger = logging.getLogger(__name__)

@receiver(post_save, sender=AutoLottery)
def create_or_update_auto_lottery_cron(sender, instance, created, **kwargs):
    """
    Create or update periodic task for AutoLottery.
    If newly activated, immediately create first Lottery.
    """
    name = f"create_lottery_from_auto_lottery_{instance.id}"
    # determine interval
    unit = instance.frequency_unit
    freq = instance.frequency or 1
    if unit == "minutes":
        every, period = freq, IntervalSchedule.MINUTES
    elif unit == "hours":
        every, period = freq, IntervalSchedule.HOURS
    elif unit == "days":
        every, period = freq, IntervalSchedule.DAYS
    elif unit == "months":
        every, period = freq * 30, IntervalSchedule.DAYS
    else:
        every, period = 1, IntervalSchedule.DAYS

    schedule, _ = IntervalSchedule.objects.get_or_create(every=every, period=period)

    if instance.is_active:
        PeriodicTask.objects.update_or_create(
            name=name,
            defaults={
                "task": "fortunaisk.tasks.create_lottery_from_auto_lottery",
                "interval": schedule,
                "args": json.dumps([instance.id]),
                "enabled": True,
            },
        )
        logger.info(f"Scheduled cron '{name}' for AutoLottery '{instance.name}'")
        if created:
            try:
                lot = instance.create_lottery()
                logger.info(f"Initial Lottery '{lot.lottery_reference}' created")
                # private=False to announce new lottery publically
                embed = build_embed(
                    title="🎲 AutoLottery Activated",
                    description=f"AutoLottery **{instance.name}** is now active.",
                    level="info",
                )
                notify_discord_or_fallback(users=None, embed=embed)
            except Exception as e:
                logger.error(f"Failed to create initial lottery: {e}", exc_info=True)
    else:
        # deactivate → delete cron
        try:
            PeriodicTask.objects.get(name=name).delete()
            logger.info(f"Deleted cron '{name}' (deactivated)")
        except PeriodicTask.DoesNotExist:
            pass


@receiver(post_delete, sender=AutoLottery)
def delete_auto_lottery_cron(sender, instance, **kwargs):
    """
    Delete periodic task when AutoLottery is deleted.
    """
    name = f"create_lottery_from_auto_lottery_{instance.id}"
    try:
        PeriodicTask.objects.get(name=name).delete()
        logger.info(f"Deleted cron '{name}' on AutoLottery delete")
    except PeriodicTask.DoesNotExist:
        pass
