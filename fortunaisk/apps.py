# fortunaisk/apps.py

# Standard Library
import logging
import sys
from importlib import import_module

# Django
from django.apps import AppConfig, apps
from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)


class FortunaIskConfig(AppConfig):
    """
    Django application configuration for FortunaIsk.

    Handles initialization of the application, including signal registration
    and configuration of periodic tasks for lottery automation.
    """

    name = "fortunaisk"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        """
        Initializes the application when Django starts.

        This method:
        1. Loads signal handlers for event processing
        2. Sets up periodic tasks for automated lottery operations
        3. Checks for corptools dependency

        Raises:
            Logs exceptions if signal loading fails but doesn't halt startup
        """
        super().ready()

        # Load signals
        try:
            # fortunaisk
            import_module("fortunaisk.signals")
            logger.info("FortunaIsk signals loaded.")
        except Exception as e:
            logger.exception(f"Error loading signals: {e}")

        # Skip tasks configuration during tests
        if (
            "test" in sys.argv
            or "runtests.py" in sys.argv[0]
            or hasattr(settings, "TESTING")
            or "pytest" in sys.modules
        ):
            logger.info("Skipping periodic tasks setup during tests.")
            return

        # Skip during migrations
        if "migrate" in sys.argv or "makemigrations" in sys.argv:
            logger.info("Skipping periodic tasks setup during migrations.")
            return

        # Check that Celery Beat tables exist
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM django_celery_beat_crontabschedule LIMIT 1"
                )
        except Exception as e:
            logger.warning(
                f"Celery Beat tables not available, skipping periodic tasks setup: {e}"
            )
            return

        # Configure periodic tasks
        try:
            from .tasks import setup_periodic_tasks

            setup_periodic_tasks()
            logger.info("FortunaIsk periodic tasks configured.")
        except Exception as e:
            logger.exception(f"Error setting up periodic tasks: {e}")

        # Check dependencies
        if not apps.is_installed("corptools"):
            logger.warning("corptools not installed; some features disabled.")
