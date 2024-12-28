# fortunaisk/signals/autolottery_signals.py

# Standard Library
import json
import logging

# Third Party
from django_celery_beat.models import IntervalSchedule, PeriodicTask

# Django
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AutoLottery)
def create_or_update_periodic_task(sender, instance, created, **kwargs):
    """
    Crée ou met à jour une tâche périodique pour chaque AutoLottery active.
    La tâche crée une Lottery à la fréquence définie.
    """
    if instance.is_active:
        try:
            # Définir l'intervalle basé sur la fréquence et l'unité
            if instance.frequency_unit == "minutes":
                interval = instance.frequency
                period = IntervalSchedule.MINUTES
            elif instance.frequency_unit == "hours":
                interval = instance.frequency
                period = IntervalSchedule.HOURS
            elif instance.frequency_unit == "days":
                interval = instance.frequency
                period = IntervalSchedule.DAYS
            elif instance.frequency_unit == "months":
                # Approximation : 30 jours
                interval = 30 * instance.frequency
                period = IntervalSchedule.DAYS
            else:
                # Par défaut, 1 jour
                interval = 1
                period = IntervalSchedule.DAYS

            # Créer ou obtenir l'IntervalSchedule
            schedule, created_schedule = IntervalSchedule.objects.get_or_create(
                every=interval,
                period=period,
            )

            # Nom unique pour la tâche périodique basée sur l'ID de l'AutoLottery
            task_name = f"create_lottery_from_auto_lottery_{instance.id}"

            # Créer ou mettre à jour la tâche périodique
            PeriodicTask.objects.update_or_create(
                name=task_name,
                defaults={
                    "task": "fortunaisk.tasks.create_lottery_from_auto_lottery",
                    "interval": schedule,
                    "args": json.dumps([instance.id]),
                },
            )
            logger.info(
                f"Tâche périodique '{task_name}' créée/mise à jour pour AutoLottery '{instance.name}'"
            )
        except Exception as e:
            logger.error(
                f"Erreur lors de la création/mise à jour de la tâche périodique pour AutoLottery '{instance.name}': {e}"
            )
    else:
        # Si l'AutoLottery est désactivée, supprimer la tâche périodique associée
        try:
            task_name = f"create_lottery_from_auto_lottery_{instance.id}"
            periodic_task = PeriodicTask.objects.get(name=task_name)
            periodic_task.delete()
            logger.info(
                f"Tâche périodique '{task_name}' supprimée pour AutoLottery '{instance.name}'"
            )
        except PeriodicTask.DoesNotExist:
            logger.warning(
                f"Tâche périodique '{task_name}' inexistante pour AutoLottery '{instance.name}'"
            )
        except Exception as e:
            logger.error(
                f"Erreur lors de la suppression de la tâche périodique '{task_name}' pour AutoLottery '{instance.name}': {e}"
            )


@receiver(post_delete, sender=AutoLottery)
def delete_periodic_task_on_autolottery_delete(sender, instance, **kwargs):
    """
    Supprime la tâche périodique associée lorsque l'AutoLottery est supprimée.
    """
    try:
        task_name = f"create_lottery_from_auto_lottery_{instance.id}"
        periodic_task = PeriodicTask.objects.get(name=task_name)
        periodic_task.delete()
        logger.info(
            f"Tâche périodique '{task_name}' supprimée pour AutoLottery '{instance.name}'"
        )
    except PeriodicTask.DoesNotExist:
        logger.warning(
            f"Tâche périodique '{task_name}' inexistante pour AutoLottery '{instance.name}'"
        )
    except Exception as e:
        logger.error(
            f"Erreur lors de la suppression de la tâche périodique '{task_name}' pour AutoLottery '{instance.name}': {e}"
        )
