# fortunaisk/apps.py

# Standard Library
import logging
from importlib import import_module

# Django
from django.apps import AppConfig, apps

logger = logging.getLogger(__name__)


class FortunaIskConfig(AppConfig):
    name = "fortunaisk"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        super().ready()
        # Charge les signals
        try:
            # fortunaisk
            import_module("fortunaisk.signals")

            logger.info("FortunaIsk signals loaded.")
        except Exception as e:
            logger.exception(f"Error loading signals: {e}")
        # Configure périodiques
        from .tasks import setup_periodic_tasks

        setup_periodic_tasks()
        logger.info("FortunaIsk periodic tasks configured.")
        if not apps.is_installed("corptools"):
            logger.warning("corptools not installed; some features disabled.")
