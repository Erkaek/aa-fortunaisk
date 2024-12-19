# Django
from django.apps import AppConfig


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"

    def ready(self):
        # Django
        from django.db.models.signals import post_migrate

        from .tasks import setup_tasks

        post_migrate.connect(setup_tasks, sender=self)
