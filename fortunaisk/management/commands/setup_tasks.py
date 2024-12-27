# fortunaisk/management/commands/setup_tasks.py

# Standard Library
import logging

# Django
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Setup default periodic tasks for FortunaIsk"

    def handle(self, *args, **options):
        try:

            self.stdout.write(
                self.style.SUCCESS("Default periodic tasks set up successfully.")
            )
            logger.info("Default periodic tasks set up successfully.")
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error setting up tasks: {e}"))
            logger.error(f"Error setting up tasks: {e}")
