# fortunaisk/signals/autolottery_signals.py

import json
import logging
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from . import autolottery_signals  # Assurez-vous que ce fichier est bien importé
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)

@receiver(post_save, sender=AutoLottery)
def create_or_update_periodic_task(sender, instance, created, **kwargs):
    """
    Crée ou met à jour une tâche périodique chaque fois qu'une AutoLottery est créée ou mise à jour.
    Supprime la tâche si l'AutoLottery est désactivée.
    """
    task_name = f"create_lottery_auto_{instance.id}"

    if instance.is_active:
        # Mapping des unités de fréquence
        period_map = {
            "minutes": IntervalSchedule.MINUTES,
            "hours": IntervalSchedule.HOURS,
            "days": IntervalSchedule.DAYS,
            "months": IntervalSchedule.DAYS,  # Approximation pour les mois
        }

        period_type = period_map.get(instance.frequency_unit)
        if not period_type:
            logger.error(f"Unsupported frequency_unit: {instance.frequency_unit} for AutoLottery ID {instance.id}")
            return

        # Calcul de l'intervalle
        if instance.frequency_unit == "months":
            every = instance.frequency * 30  # Approximation: 1 mois = 30 jours
        else:
            every = instance.frequency

        # Créer ou obtenir l'intervalle
        interval, created_interval = IntervalSchedule.objects.get_or_create(
            every=every,
            period=period_type,
        )

        # Créer ou mettre à jour la tâche périodique
        periodic_task, created_task = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.create_lottery_from_auto",
                "interval": interval,
                "args": json.dumps([instance.id]),
            },
        )

        if created_task:
            logger.info(f"PeriodicTask '{task_name}' créée pour AutoLottery ID {instance.id}.")
        else:
            logger.info(f"PeriodicTask '{task_name}' mise à jour pour AutoLottery ID {instance.id}.")
    else:
        # Si l'AutoLottery est désactivée, supprimer la tâche périodique
        try:
            periodic_task = PeriodicTask.objects.get(name=task_name)
            periodic_task.delete()
            logger.info(f"PeriodicTask '{task_name}' supprimée car AutoLottery ID {instance.id} a été désactivée.")
        except PeriodicTask.DoesNotExist:
            logger.warning(f"PeriodicTask '{task_name}' n'existe pas lors de la désactivation de l'AutoLottery ID {instance.id}.")


@receiver(post_delete, sender=AutoLottery)
def delete_periodic_task(sender, instance, **kwargs):
    """
    Supprime la tâche périodique associée lorsqu'une AutoLottery est supprimée.
    """
    task_name = f"create_lottery_auto_{instance.id}"
    try:
        periodic_task = PeriodicTask.objects.get(name=task_name)
        periodic_task.delete()
        logger.info(f"PeriodicTask '{task_name}' supprimée pour AutoLottery ID {instance.id}.")
    except PeriodicTask.DoesNotExist:
        logger.warning(f"PeriodicTask '{task_name}' n'existe pas lors de la suppression de l'AutoLottery ID {instance.id}.")
