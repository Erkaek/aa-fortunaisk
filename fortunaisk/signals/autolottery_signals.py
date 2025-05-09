# fortunaisk/signals/autolottery_signals.py

import json
import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)

@receiver(post_save, sender=AutoLottery)
def handle_autolottery_save(sender, instance, created, **kwargs):
    """
    Create or update a periodic task for the AutoLottery.
    """
    task_name = f"create_lottery_from_auto_lottery_{instance.id}"
    if instance.is_active:
        if instance.frequency_unit == "minutes":
            every, period = instance.frequency, IntervalSchedule.MINUTES
        elif instance.frequency_unit == "hours":
            every, period = instance.frequency, IntervalSchedule.HOURS
        elif instance.frequency_unit == "days":
            every, period = instance.frequency, IntervalSchedule.DAYS
        else:
            # approximate months as 30-day blocks
            every, period = instance.frequency * 30, IntervalSchedule.DAYS

        schedule, _ = IntervalSchedule.objects.get_or_create(every=every, period=period)
        PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.create_lottery_from_auto_lottery",
                "interval": schedule,
                "args": json.dumps([instance.id]),
                "enabled": True,
            },
        )
        logger.info(f"AutoLottery periodic task '{task_name}' set to every {every} {period}.")
        if created:
            instance.create_lottery()
            logger.info(f"Created first Lottery for AutoLottery '{instance.name}'.")
    else:
        try:
            pt = PeriodicTask.objects.get(name=task_name)
            pt.delete()
            logger.info(f"Deleted periodic task '{task_name}' for deactivated AutoLottery.")
        except PeriodicTask.DoesNotExist:
            logger.warning(f"Periodic task '{task_name}' not found for deactivated AutoLottery.")

@receiver(post_delete, sender=AutoLottery)
def handle_autolottery_delete(sender, instance, **kwargs):
    task_name = f"create_lottery_from_auto_lottery_{instance.id}"
    try:
        pt = PeriodicTask.objects.get(name=task_name)
        pt.delete()
        logger.info(f"Deleted periodic task '{task_name}' on AutoLottery deletion.")
    except PeriodicTask.DoesNotExist:
        logger.warning(f"Periodic task '{task_name}' not found on AutoLottery deletion.")
