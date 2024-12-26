# fortunaisk/apps.py

# Standard Library
import logging

# Django
from django.apps import AppConfig  # type: ignore

logger = logging.getLogger(__name__)


class FortunaIskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fortunaisk"

    def ready(self) -> None:
        super().ready()
        # fortunaisk
        import fortunaisk.signals  # noqa: F401  # Re-import signals to register them

        logger.info("FortunaIsk signals loaded.")
