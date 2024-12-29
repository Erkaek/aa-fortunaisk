# fortunaisk/signals/auditlog_signals.py

# Standard Library
import datetime
import logging
from decimal import Decimal

# Django
from django.db import ProgrammingError, connection, models
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

# fortunaisk
from fortunaisk.models.auditlog import AuditLog

logger = logging.getLogger(__name__)


def table_exists(table_name: str) -> bool:
    """
    Checks if the table already exists in the database
    (prevents error 1146 during the first migration).
    """
    try:
        return table_name in connection.introspection.table_names()
    except ProgrammingError:
        return False


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


def is_fortunaisk_model(sender):
    """
    Checks if the model belongs to the 'fortunaisk' application.
    """
    return sender._meta.app_label == "fortunaisk"


@receiver(pre_save)
def auditlog_pre_save(sender, instance, **kwargs):
    if sender == AuditLog or not is_fortunaisk_model(sender):
        return
    if not instance.pk:
        # Creation case, no old version
        instance._pre_save_instance = None
    else:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._pre_save_instance = old_instance
        except sender.DoesNotExist:
            instance._pre_save_instance = None


@receiver(post_save)
def auditlog_post_save(sender, instance, created, **kwargs):
    if sender == AuditLog or not is_fortunaisk_model(sender):
        return

    # Check table existence before inserting
    if not table_exists("fortunaisk_auditlog"):
        return

    if created:
        # Creation case
        AuditLog.objects.create(
            user=None,
            action_type="create",
            model=sender.__name__,
            object_id=instance.pk,
            changes=None,
        )
    else:
        # Update case
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
    if sender == AuditLog or not is_fortunaisk_model(sender):
        return
    instance._pre_delete_instance = instance


@receiver(post_delete)
def auditlog_post_delete(sender, instance, **kwargs):
    if sender == AuditLog or not is_fortunaisk_model(sender):
        return

    if not table_exists("fortunaisk_auditlog"):
        return

    AuditLog.objects.create(
        user=None,
        action_type="delete",
        model=sender.__name__,
        object_id=instance.pk,
        changes=None,
    )
