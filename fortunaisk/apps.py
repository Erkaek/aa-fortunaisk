# Django
from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"
    verbose_name = "Fortunaisk Lottery System"

    def ready(self):
        from .tasks import setup_tasks

        post_migrate.connect(setup_tasks, sender=self)


def setup_tasks(sender, **kwargs):
    from .models import Lottery

    active_lotteries = Lottery.objects.filter(is_active=True)
    for lottery in active_lotteries:
        # Initialiser les tâches périodiques si nécessaire
        pass
