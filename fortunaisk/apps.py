from django.apps import AppConfig

class FortunaiskConfig(AppConfig):
    name = 'fortunaisk'

    def ready(self):
        from .tasks import setup_tasks
        from django.db.models.signals import post_migrate
        post_migrate.connect(setup_tasks, sender=self)