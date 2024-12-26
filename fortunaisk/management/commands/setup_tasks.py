# fortunaisk/management/commands/setup_tasks.py

# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import CrontabSchedule, PeriodicTask

# Django
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Setup default periodic tasks for FortunaIsk"

    def handle(self, *args, **options):
        try:
            # check_lotteries => ex. toutes les 15 minutes
            schedule_check, _ = CrontabSchedule.objects.get_or_create(
                minute="*/15",
                hour="*",
                day_of_month="*",
                month_of_year="*",
                day_of_week="*",
            )
            PeriodicTask.objects.update_or_create(
                name="check_lotteries",
                defaults={
                    "task": "fortunaisk.tasks.check_lotteries",
                    "crontab": schedule_check,
                    "args": json.dumps([]),
                },
            )

            # process_wallet_tickets => ex. toutes les 5 minutes
            schedule_wallet, _ = CrontabSchedule.objects.get_or_create(
                minute="*/5",
                hour="*",
                day_of_month="*",
                month_of_year="*",
                day_of_week="*",
            )
            PeriodicTask.objects.update_or_create(
                name="process_wallet_tickets",
                defaults={
                    "task": "fortunaisk.tasks.process_wallet_tickets",
                    "crontab": schedule_wallet,
                    "args": json.dumps([]),
                },
            )

            self.stdout.write(self.style.SUCCESS("Default tasks set up successfully."))
            logger.info("Default periodic tasks set up successfully.")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error setting up tasks: {e}"))
            logger.error(f"Error setting up tasks: {e}")
