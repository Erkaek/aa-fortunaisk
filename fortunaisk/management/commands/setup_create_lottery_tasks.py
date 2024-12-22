# fortunaisk/management/commands/setup_create_lottery_tasks.py
import json
import logging

from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask

from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up or update periodic tasks for all active AutoLotteries."

    def handle(self, *args, **options):
        self.setup_auto_lottery_tasks()

    def setup_auto_lottery_tasks(self):
        autolotteries = AutoLottery.objects.filter(is_active=True)
        for autolottery in autolotteries:
            task_name = f"create_lottery_auto_{autolottery.id}"
            # convert frequency unit to IntervalSchedule period
            period_type = self.get_period_type(autolottery.frequency_unit)
            if not period_type:
                logger.error(f"Unsupported frequency_unit: {autolottery.frequency_unit}")
                continue

            interval, _ = IntervalSchedule.objects.get_or_create(
                every=self.get_every_value(autolottery.frequency, autolottery.frequency_unit),
                period=period_type,
            )
            task, created = PeriodicTask.objects.update_or_create(
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

    def get_period_type(self, frequency_unit: str):
        unit_map = {
            "minutes": IntervalSchedule.MINUTES,
            "hours": IntervalSchedule.HOURS,
            "days": IntervalSchedule.DAYS,
        }
        # months approximated to 30 days
        return unit_map.get(frequency_unit, None)

    def get_every_value(self, frequency: int, frequency_unit: str) -> int:
        if frequency_unit == "months":
            return frequency * 30
        return frequency
