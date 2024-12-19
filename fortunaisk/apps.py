# Django
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"

    def ready(self):
        from .tasks import setup_tasks

        post_migrate.connect(setup_tasks, sender=self)
