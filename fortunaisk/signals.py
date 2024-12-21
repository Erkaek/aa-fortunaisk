# fortunaisk/signals.py

from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import AutoLottery
from django_celery_beat.models import PeriodicTask

@receiver(pre_delete, sender=AutoLottery)
def delete_periodic_task(sender, instance, **kwargs):
    task_name = f"AutoLottery_{instance.id}"
    PeriodicTask.objects.filter(name=task_name).delete()