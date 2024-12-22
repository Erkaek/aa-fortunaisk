# fortunaisk/management/commands/setup_tasks.py
# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Setup periodic tasks for FortunaIsk"

    def handle(self, *args, **options):
        try:
            # check_lotteries every 15 minutes
            schedule_15, _ = IntervalSchedule.objects.get_or_create(
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
            schedule_5, _ = IntervalSchedule.objects.get_or_create(
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

            # Optionally, run setup_create_lottery_tasks
            # fortunaisk
            from fortunaisk.management.commands.setup_create_lottery_tasks import (
                Command as SetupAutoLotteryCommand,
            )

            SetupAutoLotteryCommand().setup_auto_lottery_tasks()

            self.stdout.write(
                self.style.SUCCESS("Periodic tasks have been set up successfully.")
            )
            logger.info("Periodic tasks have been set up successfully.")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error setting up tasks: {e}"))
            logger.error(f"Error setting up tasks: {e}")
