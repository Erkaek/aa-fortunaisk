# fortunaisk/apps.py
"""Django AppConfig for the FortunaIsk lottery application."""

# Django
from django.apps import AppConfig


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"

    def ready(self):
        # Importer les tâches périodiques pour s'assurer qu'elles sont configurées au démarrage
        from .tasks import setup_tasks

        setup_tasks()
