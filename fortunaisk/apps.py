# fortunaisk/apps.py
"""Django AppConfig for the FortunaIsk lottery application."""

# Django
from django.apps import AppConfig

from .tasks import setup_tasks


class FortunaIskConfig(AppConfig):
    name = "fortunaisk"

    def ready(self):
        # Define a signal receiver that accepts **kwargs
        def run_setup_tasks(sender, **kwargs):
            setup_tasks()  # Call your existing function
