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

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AutoLottery)
def create_or_update_periodic_task(sender, instance, created, **kwargs):
    """
    Creates or updates a periodic task for each active AutoLottery.
    The task creates a Lottery at the defined frequency.
    Additionally, creates the first Lottery immediately upon creation of the AutoLottery.
    """
    if instance.is_active:
        try:
            # Define the interval based on frequency and unit
            if instance.frequency_unit == "minutes":
                interval = instance.frequency
                period = IntervalSchedule.MINUTES
            elif instance.frequency_unit == "hours":
                interval = instance.frequency
                period = IntervalSchedule.HOURS
            elif instance.frequency_unit == "days":
                interval = instance.frequency
                period = IntervalSchedule.DAYS
            elif instance.frequency_unit == "months":
                # Approximation: 30 days
                interval = 30 * instance.frequency
                period = IntervalSchedule.DAYS
            else:
                # Default to 1 day
                interval = 1
                period = IntervalSchedule.DAYS

            # Create or get the IntervalSchedule
            schedule, created_schedule = IntervalSchedule.objects.get_or_create(
                every=interval,
                period=period,
            )

            # Unique name for the periodic task based on AutoLottery ID
            task_name = f"create_lottery_from_auto_lottery_{instance.id}"

            # Create or update the PeriodicTask
            PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "task": "fortunaisk.tasks.create_lottery_from_auto_lottery",
                    "interval": schedule,
                    "args": json.dumps([instance.id]),
                },
            )
            logger.info(
                f"Periodic task '{task_name}' created/updated for AutoLottery '{instance.name}'."
            )

            # If the AutoLottery was just created, create the first Lottery immediately
            if created:
                instance.create_lottery()
                logger.info(
                    f"First Lottery created for AutoLottery '{instance.name}' upon creation."
                )
        except Exception as e:
            logger.error(
                f"Error creating/updating periodic task for AutoLottery '{instance.name}': {e}"
            )
    else:
        # If AutoLottery is deactivated, delete the associated periodic task
        try:
            task_name = f"create_lottery_from_auto_lottery_{instance.id}"
            periodic_task = PeriodicTask.objects.get(name=task_name)
            periodic_task.delete()
            logger.info(
                f"Periodic task '{task_name}' deleted for AutoLottery '{instance.name}'."
            )
        except PeriodicTask.DoesNotExist:
            logger.warning(
                f"Periodic task '{task_name}' does not exist for AutoLottery '{instance.name}'."
            )
        except Exception as e:
            logger.error(
                f"Error deleting periodic task '{task_name}' for AutoLottery '{instance.name}': {e}"
            )


@receiver(post_delete, sender=AutoLottery)
def delete_periodic_task_on_autolottery_delete(sender, instance, **kwargs):
    """
    Deletes the associated periodic task when an AutoLottery is deleted.
    """
    try:
        task_name = f"create_lottery_from_auto_lottery_{instance.id}"
        periodic_task = PeriodicTask.objects.get(name=task_name)
        periodic_task.delete()
        logger.info(
            f"Periodic task '{task_name}' deleted for AutoLottery '{instance.name}'."
        )
    except PeriodicTask.DoesNotExist:
        logger.warning(
            f"Periodic task '{task_name}' does not exist for AutoLottery '{instance.name}'."
        )
    except Exception as e:
        logger.error(
            f"Error deleting periodic task '{task_name}' for AutoLottery '{instance.name}': {e}"
        )
