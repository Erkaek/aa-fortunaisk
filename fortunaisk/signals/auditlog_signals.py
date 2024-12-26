# fortunaisk/signals/auditlog_signals.py

# Standard Library
import logging
from django.db.models.signals import pre_save, post_save, pre_delete, post_delete
from django.dispatch import receiver
from django.apps import apps

# fortunaisk
from fortunaisk.models.auditlog import AuditLog

logger = logging.getLogger(__name__)


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
                'old': old_value,
                'new': new_value
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
            user=getattr(instance, 'modified_by', None),  # Assuming 'modified_by' is set
            action_type='create',
            model=sender.__name__,
            object_id=instance.pk,
            changes=None  # No changes on creation
        )
    else:
        # Log update
        old_instance = getattr(instance, '_pre_save_instance', None)
        if not old_instance:
            return  # Unable to retrieve old instance, skip logging

        changes = get_changes(old_instance, instance)
        if changes:
            AuditLog.objects.create(
                user=getattr(instance, 'modified_by', None),  # Assuming 'modified_by' is set
                action_type='update',
                model=sender.__name__,
                object_id=instance.pk,
                changes=changes
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
        user=getattr(instance, 'modified_by', None),  # Assuming 'modified_by' is set
        action_type='delete',
        model=sender.__name__,
        object_id=instance.pk,
        changes=None  # No changes on deletion
    )
