# fortunaisk/signals/setup_tasks_signal.py

# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask  # type: ignore

# Django
from django.db.models.signals import post_migrate  # type: ignore
from django.dispatch import receiver  # type: ignore

# fortunaisk
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def setup_periodic_tasks(sender, **kwargs):
    """
    Sets up periodic Celery tasks after migrations.
    This includes the default tasks only.
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

        # 2. Configure tasks for active AutoLotteries is handled by signals/autolottery_signals.py
        # No longer set up AutoLottery tasks here to avoid duplication

        logger.info(
            "All periodic tasks for AutoLotteries are handled by autolottery_signals.py."
        )

    except Exception as e:
        logger.exception(f"Error setting up periodic tasks: {e}")
