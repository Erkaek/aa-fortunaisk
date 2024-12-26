# fortunaisk/signals.py

# Standard Library
import datetime
import json
import logging
from decimal import Decimal

# Third Party
from django_celery_beat.models import CrontabSchedule, PeriodicTask

# Django
from django.core.management import call_command
from django.db import models
from django.db.models.signals import (
    post_delete,
    post_migrate,
    post_save,
    pre_delete,
    pre_save,
)
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models import AuditLog, AutoLottery, Lottery
from fortunaisk.tasks import create_lottery_from_auto

logger = logging.getLogger(__name__)


########################
#  post_migrate signal #
########################


@receiver(post_migrate)
def run_setup_tasks(sender, **kwargs):
    """
    Après la migration du module 'fortunaisk',
    on exécute la management command 'setup_tasks' pour configurer
    check_lotteries et process_wallet_tickets.
    """
    if sender.name == "fortunaisk":
        try:
            call_command("setup_tasks")
            logger.info("Ran setup_tasks after migrate.")
        except Exception as e:
            logger.exception(f"Error running setup_tasks after migrate: {e}")


########################################################
#  AutoLottery signals : création / suppression tasks  #
########################################################


def make_crontab_from_frequency(frequency, frequency_unit):
    """
    Convertir (freq, freq_unit) en un CrontabSchedule.
    """
    if frequency_unit == "months":
        return CrontabSchedule.objects.get_or_create(
            minute="30",
            hour="18",
            day_of_month="26",
            month_of_year=f"*/{frequency}",
            day_of_week="*",
        )
    elif frequency_unit == "days":
        return CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="0",
            day_of_month=f"*/{frequency}",
            month_of_year="*",
            day_of_week="*",
        )
    elif frequency_unit == "hours":
        return CrontabSchedule.objects.get_or_create(
            minute="0",
            hour=f"*/{frequency}",
            day_of_month="*",
            month_of_year="*",
            day_of_week="*",
        )
    elif frequency_unit == "minutes":
        return CrontabSchedule.objects.get_or_create(
            minute=f"*/{frequency}",
            hour="*",
            day_of_month="*",
            month_of_year="*",
            day_of_week="*",
        )
    else:
        # fallback
        return CrontabSchedule.objects.get_or_create(
            minute="0",
            hour="0",
            day_of_month="*",
            month_of_year="*",
            day_of_week="*",
        )


@receiver(post_save, sender=AutoLottery)
def create_or_update_autolottery_task(sender, instance, created, **kwargs):
    """
    Quand on crée ou on modifie une AutoLottery :
    - si is_active => on crée/MAJ la tâche CrontabSchedule
    - si created ET is_active => on crée immédiatement une première Lottery
    """
    task_name = f"create_lottery_auto_{instance.id}"

    if instance.is_active:
        crontab, _ = make_crontab_from_frequency(
            instance.frequency, instance.frequency_unit
        )
        _, created_task = PeriodicTask.objects.update_or_create(
            name=task_name,
            defaults={
                "task": "fortunaisk.tasks.create_lottery_from_auto",
                "crontab": crontab,
                "args": json.dumps([instance.id]),
            },
        )
        logger.info(
            f"PeriodicTask '{task_name}' created/updated for AutoLottery {instance.name}."
        )

        if created and instance.is_active:
            try:
                create_lottery_from_auto(instance.id)
                logger.info(f"Initial Lottery created for AutoLottery {instance.name}.")
            except Exception as e:
                logger.exception(
                    f"Error creating initial Lottery for AutoLottery {instance.id}: {e}"
                )
    else:
        # si pas active => on supprime la PeriodicTask
        try:
            PeriodicTask.objects.get(name=task_name).delete()
            logger.info(
                f"PeriodicTask '{task_name}' deleted (AutoLottery {instance.name} deactivated)."
            )
        except PeriodicTask.DoesNotExist:
            logger.warning(
                f"PeriodicTask '{task_name}' does not exist when deactivating AutoLottery {instance.name}."
            )


@receiver(post_delete, sender=AutoLottery)
def delete_autolottery_task(sender, instance, **kwargs):
    """
    Quand on supprime une AutoLottery, on supprime la PeriodicTask correspondante.
    """
    task_name = f"create_lottery_auto_{instance.id}"
    try:
        PeriodicTask.objects.get(name=task_name).delete()
        logger.info(f"PeriodicTask '{task_name}' deleted (AutoLottery was removed).")
    except PeriodicTask.DoesNotExist:
        logger.warning(
            f"PeriodicTask '{task_name}' does not exist on AutoLottery deletion."
        )


###################
#  AuditLog stuff #
###################


def serialize_value(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    elif isinstance(value, datetime.date):
        return value.isoformat()
    elif isinstance(value, datetime.time):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return str(value)
    elif isinstance(value, models.Model):
        return str(value)
    else:
        return str(value)


def get_changes(old_instance, new_instance):
    changes = {}
    for field in new_instance._meta.fields:
        field_name = field.name
        old_value = getattr(old_instance, field_name, None)
        new_value = getattr(new_instance, field_name, None)
        if old_value != new_value:
            changes[field_name] = {
                "old": serialize_value(old_value),
                "new": serialize_value(new_value),
            }
    return changes


@receiver(pre_save)
def auditlog_pre_save(sender, instance, **kwargs):
    if sender == AuditLog:
        return
    if not instance.pk:
        instance._pre_save_instance = None
    else:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._pre_save_instance = old_instance
        except sender.DoesNotExist:
            instance._pre_save_instance = None


@receiver(post_save)
def auditlog_post_save(sender, instance, created, **kwargs):
    if sender == AuditLog:
        return
    if created:
        AuditLog.objects.create(
            user=None,
            action_type="create",
            model=sender.__name__,
            object_id=instance.pk,
            changes=None,
        )
    else:
        old_instance = getattr(instance, "_pre_save_instance", None)
        if not old_instance:
            return
        changes = get_changes(old_instance, instance)
        if changes:
            AuditLog.objects.create(
                user=None,
                action_type="update",
                model=sender.__name__,
                object_id=instance.pk,
                changes=changes,
            )


@receiver(pre_delete)
def auditlog_pre_delete(sender, instance, **kwargs):
    if sender == AuditLog:
        return
    instance._pre_delete_instance = instance


@receiver(post_delete)
def auditlog_post_delete(sender, instance, **kwargs):
    if sender == AuditLog:
        return
    AuditLog.objects.create(
        user=None,
        action_type="delete",
        model=sender.__name__,
        object_id=instance.pk,
        changes=None,
    )


#########################
#  Lottery status stuff #
#########################


@receiver(pre_save, sender=Lottery)
def lottery_pre_save(sender, instance, **kwargs):
    if instance.pk:
        try:
            old_instance = Lottery.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Lottery.DoesNotExist:
            instance._old_status = None
    else:
        instance._old_status = None


@receiver(post_save, sender=Lottery)
def lottery_post_save(sender, instance, created, **kwargs):
    # ex. envoi d'un embed indiquant la distribution, etc.
    # ou usage d'autres signaux custom
    pass
