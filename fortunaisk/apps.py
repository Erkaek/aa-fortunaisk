# Django
from django.apps import AppConfig


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"
    label = "fortunaisk"
    verbose_name = "FortunaISK App"

    def ready(self):
        # Alliance Auth
        from allianceauth.services.hooks import get_hooks

        # Vérifie que Celery est configuré
        hooks = get_hooks("celery_hook")
        if hooks:
            from .tasks import process_ticket_purchases

            self.logger.info("Celery task for ticket purchase loaded.")
