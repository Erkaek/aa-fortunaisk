# fortunaisk/apps.py
"""Django AppConfig for the FortunaIsk lottery application."""

# Django
from django.apps import AppConfig


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"

    def ready(self):
        # Import here to ensure it is only executed after Django is fully loaded
        from .tasks import setup_tasks

        setup_tasks()
