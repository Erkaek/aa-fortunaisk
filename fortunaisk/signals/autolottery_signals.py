# fortunaisk/signals/autolottery_signals.py

# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import (  # type: ignore
    CrontabSchedule,
    IntervalSchedule,
    PeriodicTask,
)

# Django
from django.db.models.signals import post_delete, post_save  # type: ignore
from django.dispatch import receiver  # type: ignore

# fortunaisk
from fortunaisk.models import AutoLottery
from fortunaisk.tasks import create_lottery_from_auto

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AutoLottery)
def create_or_update_periodic_task(sender, instance, created, **kwargs):
    """
    Creates or updates a periodic task each time an AutoLottery is created or updated.
    If AutoLottery is active, creates a Lottery immediately.
    """
    task_name = f"create_lottery_auto_{instance.id}"

    if instance.is_active:
        # Mapping frequency units to schedule types
        frequency_unit = instance.frequency_unit
        frequency_value = instance.frequency

        if frequency_unit == "months":
            # Schedule monthly tasks using CrontabSchedule
            # Example: Run on the 1st day of every 'frequency_value' months at midnight
            schedule, created_schedule = CrontabSchedule.objects.get_or_create(
                minute="0",
                hour="0",
                day_of_month="1",
                month_of_year=f"*/{frequency_value}",
                day_of_week="*",
            )
            # Create or update PeriodicTask
            periodic_task, created_task = PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "task": "fortunaisk.tasks.create_lottery_from_auto",
                    "crontab": schedule,
                    "args": json.dumps([instance.id]),
                },
            )
        else:
            # For other units, use IntervalSchedule
            period_map = {
                "minutes": IntervalSchedule.MINUTES,
                "hours": IntervalSchedule.HOURS,
                "days": IntervalSchedule.DAYS,
            }

            period_type = period_map.get(frequency_unit)
            if not period_type:
                logger.error(
                    f"Unsupported frequency_unit: {frequency_unit} for AutoLottery ID {instance.id}"
                )
                return

            # Calculate the interval
            every = frequency_value

            # Create or get the IntervalSchedule
            interval, created_interval = IntervalSchedule.objects.get_or_create(
                every=every,
                period=period_type,
            )

            # Create or update the PeriodicTask
            periodic_task, created_task = PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "task": "fortunaisk.tasks.create_lottery_from_auto",
                    "interval": interval,
                    "args": json.dumps([instance.id]),
                },
            )

        if periodic_task:
            logger.info(
                f"PeriodicTask '{task_name}' {'created' if created_task else 'updated'} for AutoLottery ID {instance.id}."
            )

        # Create a Lottery immediately
        try:
            create_lottery_from_auto.delay(instance.id)
            logger.info(
                f"Initial Lottery created immediately for AutoLottery ID {instance.id}."
            )
        except Exception as e:
            logger.exception(
                f"Error creating initial Lottery for AutoLottery ID {instance.id}: {e}"
            )
    else:
        # If AutoLottery is deactivated, delete the periodic task
        try:
            periodic_task = PeriodicTask.objects.get(name=task_name)
            periodic_task.delete()
            logger.info(
                f"PeriodicTask '{task_name}' deleted as AutoLottery ID {instance.id} was deactivated."
            )
        except PeriodicTask.DoesNotExist:
            logger.warning(
                f"PeriodicTask '{task_name}' does not exist when trying to deactivate AutoLottery ID {instance.id}."
            )


@receiver(post_delete, sender=AutoLottery)
def delete_periodic_task(sender, instance, **kwargs):
    """
    Deletes the periodic task associated when an AutoLottery is deleted.
    """
    task_name = f"create_lottery_auto_{instance.id}"
    try:
        periodic_task = PeriodicTask.objects.get(name=task_name)
        periodic_task.delete()
        logger.info(
            f"PeriodicTask '{task_name}' deleted for AutoLottery ID {instance.id}."
        )
    except PeriodicTask.DoesNotExist:
        logger.warning(
            f"PeriodicTask '{task_name}' does not exist when trying to delete AutoLottery ID {instance.id}."
        )
