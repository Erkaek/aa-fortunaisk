# fortunaisk/apps.py

# Standard Library
import logging

# Django
from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"
    label = "fortunaisk"
    verbose_name = "Fortunaisk App"

    def ready(self):
        from .models import Lottery

        def setup_periodic_tasks(sender, **kwargs):
            try:
                # Configure periodic tasks for all active lotteries
                active_lotteries = Lottery.objects.filter(status="active")
                for lottery in active_lotteries:
                    lottery.setup_periodic_task()
                logger.info(
                    "Periodic tasks successfully configured for active lotteries."
                )
            except Exception as e:
                logger.error(f"Error setting up periodic tasks: {e}")

        post_migrate.connect(setup_periodic_tasks, sender=self)
