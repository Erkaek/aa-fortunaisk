# Django
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"
    verbose_name = "Fortunaisk Lottery System"

    def ready(self):
        from .models import Lottery

        def setup_tasks(sender, **kwargs):
            Lottery.objects.filter(status="active").update()

        post_migrate.connect(setup_tasks, sender=self)
