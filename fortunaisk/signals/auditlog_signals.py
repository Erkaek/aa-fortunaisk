# fortunaisk/signals/auditlog_signals.py

# Standard Library
import datetime
import logging
from decimal import Decimal

# Django
from django.db import models  # Importation ajoutée
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models.auditlog import AuditLog

logger = logging.getLogger(__name__)


def serialize_value(value):
    """
    Serialize values to ensure JSON compatibility.
    """
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
        return value


def get_changes(old_instance, new_instance):
    """
    Compare old and new instances and return a dictionary of changes.
    """
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
    """
    Signal to capture the state of the instance before saving.
    """
    if sender == AuditLog:
        return  # Avoid logging AuditLog actions

    if not instance.pk:
        # Instance is being created, no old_instance exists
        instance._pre_save_instance = None
    else:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._pre_save_instance = old_instance
        except sender.DoesNotExist:
            instance._pre_save_instance = None


@receiver(post_save)
def auditlog_post_save(sender, instance, created, **kwargs):
    """
    Signal to log create and update actions.
    """
    if sender == AuditLog:
        return  # Avoid logging AuditLog actions

    if created:
        # Log creation
        AuditLog.objects.create(
            user=None,  # Aucun utilisateur défini sans middleware
            action_type="create",
            model=sender.__name__,
            object_id=instance.pk,
            changes=None,  # Pas de changements lors de la création
        )
    else:
        # Log update
        old_instance = getattr(instance, "_pre_save_instance", None)
        if not old_instance:
            return  # Impossible de récupérer l'ancienne instance, sauter le logging

        changes = get_changes(old_instance, instance)
        if changes:
            AuditLog.objects.create(
                user=None,  # Aucun utilisateur défini sans middleware
                action_type="update",
                model=sender.__name__,
                object_id=instance.pk,
                changes=changes,
            )


@receiver(pre_delete)
def auditlog_pre_delete(sender, instance, **kwargs):
    """
    Signal to capture the state of the instance before deletion.
    """
    if sender == AuditLog:
        return  # Avoid logging AuditLog actions

    instance._pre_delete_instance = instance


@receiver(post_delete)
def auditlog_post_delete(sender, instance, **kwargs):
    """
    Signal to log delete actions.
    """
    if sender == AuditLog:
        return  # Avoid logging AuditLog actions

    AuditLog.objects.create(
        user=None,  # Aucun utilisateur défini sans middleware
        action_type="delete",
        model=sender.__name__,
        object_id=instance.pk,
        changes=None,  # Pas de changements lors de la suppression
    )
