# fortunaisk/apps.py
import importlib
import logging

from django.apps import AppConfig, apps

logger = logging.getLogger(__name__)

class FortunaIskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fortunaisk"

    def ready(self) -> None:
        super().ready()

        # 1) Charger vos signals
        try:
            importlib.import_module("fortunaisk.signals")
            logger.info("FortunaIsk signals loaded.")
        except Exception as e:
            logger.exception(f"Failed to load FortunaIsk signals: {e}")

        # 2) Vérifier corptools
        if not apps.is_installed("corptools"):
            logger.warning(
                "The 'corptools' application is not installed. "
                "Some ticket processing functionalities will be unavailable."
            )

        # 3) Configurer systématiquement les tâches périodiques
        try:
            # On importe la fonction qui crée/maj les cron
            from .tasks import setup_periodic_tasks
            setup_periodic_tasks()
            logger.info("FortunaIsk periodic tasks configured.")
        except Exception as e:
            logger.exception(f"Failed to configure periodic tasks: {e}")
