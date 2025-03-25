# Standard Library
import importlib
import logging

# Django
from django.apps import AppConfig, apps

logger = logging.getLogger(__name__)


class FortunaIskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fortunaisk"

    def ready(self) -> None:
        super().ready()

        # Attempt to import signals
        try:
            importlib.import_module("fortunaisk.signals")
            logger.info("FortunaIsk signals loaded.")
        except Exception as e:
            logger.exception(f"Failed to load FortunaIsk signals: {e}")

        # Check if corptools is installed (warn if not)
        if not apps.is_installed("corptools"):
            logger.warning(
                "The 'corptools' application is not installed. "
                "Some ticket processing functionalities will be unavailable."
            )
