# fortunaisk/signals/autolottery_signals.py

# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import AutoLottery
from fortunaisk.notifications import build_embed, notify_discord_or_fallback

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AutoLottery)
def create_or_update_auto_lottery_cron(sender, instance, created, **kwargs):
    """
    On each AutoLottery save:
      - (Re)create or update its PeriodicTask
      - Set `enabled` to match `is_active` value
      - Send an initial Discord notification if it's being created
    """
    name = f"create_lottery_from_auto_lottery_{instance.id}"
    # -- Calculate frequency in minutes/days/etc. --
    unit = instance.frequency_unit
    freq = instance.frequency or 1
    if unit == "minutes":
        every, period = freq, IntervalSchedule.MINUTES
    elif unit == "hours":
        every, period = freq, IntervalSchedule.HOURS
    elif unit == "days":
        every, period = freq, IntervalSchedule.DAYS
    elif unit == "months":
        # Convert months to days
        every, period = freq * 30, IntervalSchedule.DAYS
    else:
        every, period = 1, IntervalSchedule.DAYS

    schedule, _ = IntervalSchedule.objects.get_or_create(every=every, period=period)

    # Update (or create) the task, disabling it if is_active=False
    task, created_task = PeriodicTask.objects.update_or_create(
        name=name,
        defaults={
            "task": "fortunaisk.tasks.create_lottery_from_auto_lottery",
            "interval": schedule,
            "args": json.dumps([instance.id]),
            "enabled": instance.is_active,
        },
    )
    logger.info(
        f"{'Created' if created_task else 'Updated'} cron '{name}' "
        f"for AutoLottery '{instance.name}', enabled={instance.is_active}"
    )

    # If we just created the AutoLottery AND it's active,
    # immediately create the first Lottery and notify Discord
    if created and instance.is_active:
        try:
            instance.create_lottery()
            embed = build_embed(
                title="🎲 AutoLottery Activated",
                description=f"AutoLottery **{instance.name}** is now active.",
                level="success",
            )
            notify_discord_or_fallback(
                users=None,
                event="autolottery_activated",
                embed=embed,
                private=False,
            )
        except Exception as e:
            logger.error(f"Failed to create initial lottery: {e}", exc_info=True)


@receiver(post_delete, sender=AutoLottery)
def delete_auto_lottery_cron(sender, instance, **kwargs):
    """
    When an AutoLottery is deleted, delete its task AND send notification.
    """
    name = f"create_lottery_from_auto_lottery_{instance.id}"
    try:
        PeriodicTask.objects.get(name=name).delete()
        logger.info(f"Deleted cron '{name}' on AutoLottery delete")
    except PeriodicTask.DoesNotExist:
        logger.info(f"No cron '{name}' to delete on AutoLottery delete")

    embed = build_embed(
        title="🗑️ AutoLottery Deleted",
        description=f"AutoLottery **{instance.name}** has been deleted.",
        level="warning",
    )
    notify_discord_or_fallback(
        users=None,
        event="autolottery_deleted",
        embed=embed,
        private=False,
    )
