# fortunaisk/apps.py

# Standard Library
import logging
from importlib import import_module

# Django
from django.apps import AppConfig, apps

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
        
        # Configure periodic tasks
        from .tasks import setup_periodic_tasks

        setup_periodic_tasks()
        logger.info("FortunaIsk periodic tasks configured.")
        
        # Check dependencies
        if not apps.is_installed("corptools"):
            logger.warning("corptools not installed; some features disabled.")
