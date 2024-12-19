# Django
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"
    verbose_name = "Fortunaisk Lottery System"

    def ready(self):
        from .tasks import setup_tasks  # Assurez-vous que cette ligne est correcte

        setup_tasks()
