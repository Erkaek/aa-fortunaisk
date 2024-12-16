# Django
from django.apps import AppConfig
from django.db.models.signals import post_migrate  # Import manquant


class FortunaiskConfig(AppConfig):
    name = "fortunaisk"
    label = "fortunaisk"
    verbose_name = "FortunaISK App"

    def ready(self):
        from .models import TicketPurchase

        def setup_periodic_tasks(sender, **kwargs):
            TicketPurchase.objects.setup_periodic_task()
            print("Celery Beat task 'Process Ticket Purchases' has been set up.")

        post_migrate.connect(setup_periodic_tasks, sender=self)


# Ligne vide à la fin du fichier
