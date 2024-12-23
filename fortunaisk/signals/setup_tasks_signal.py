# fortunaisk/signals/setup_tasks_signal.py

# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def setup_periodic_tasks(sender, **kwargs):
    """
    Sets up periodic Celery tasks after migrations.
    This includes the default tasks and those for AutoLotteries.
    """
    if sender.name != "fortunaisk":
        return  # Avoid multiple executions

    try:
        # 1. Configure default tasks
        # check_lotteries every 15 minutes
        schedule_15, created = IntervalSchedule.objects.get_or_create(
            every=15,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="check_lotteries",
            defaults={
                "task": "fortunaisk.tasks.check_lotteries",
                "interval": schedule_15,
                "args": json.dumps([]),
            },
        )

        # process_wallet_tickets every 5 minutes
        schedule_5, created = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )
        PeriodicTask.objects.update_or_create(
            name="process_wallet_tickets",
            defaults={
                "task": "fortunaisk.tasks.process_wallet_tickets",
                "interval": schedule_5,
                "args": json.dumps([]),
            },
        )

        logger.info("Default periodic tasks have been set up successfully.")

        # 2. Configure tasks for active AutoLotteries
        active_autolotteries = AutoLottery.objects.filter(is_active=True)
        for autolottery in active_autolotteries:
            task_name = f"create_lottery_auto_{autolottery.id}"
            # Convert frequency_unit to IntervalSchedule.period
            period_map = {
                "minutes": IntervalSchedule.MINUTES,
                "hours": IntervalSchedule.HOURS,
                "days": IntervalSchedule.DAYS,
                "months": IntervalSchedule.DAYS,  # Approximation
            }
            period_type = period_map.get(autolottery.frequency_unit)
            if not period_type:
                logger.error(
                    f"Unsupported frequency_unit: {autolottery.frequency_unit}"
                )
                continue

            # For months, approximate to 30 days
            if autolottery.frequency_unit == "months":
                every = autolottery.frequency * 30
            else:
                every = autolottery.frequency

            interval, created = IntervalSchedule.objects.get_or_create(
                every=every,
                period=period_type,
            )

            # Avoid creating multiple tasks
            PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "task": "fortunaisk.tasks.create_lottery_from_auto",
                    "interval": interval,
                    "args": json.dumps([autolottery.id]),
                },
            )
            if created:
                logger.info(f"Periodic task '{task_name}' created.")
            else:
                logger.info(f"Periodic task '{task_name}' updated.")

        logger.info(
            "All periodic tasks for AutoLotteries have been set up successfully."
        )

    except Exception as e:
        logger.exception(f"Error setting up periodic tasks: {e}")
