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
    Vérifie si la table `table_name` existe déjà dans la base de données.
    """
    try:
        return table_name in connection.introspection.table_names()
    except ProgrammingError:
        # En cas de problème d'introspection (pendant la migration), on retourne False
        return False


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
        return str(value)  # fallback, au cas où


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
    Capture l'état de l'instance avant la sauvegarde (pour comparer ensuite).
    """
    # Éviter la récursion sur AuditLog lui-même
    if sender == AuditLog:
        return

    if not instance.pk:
        # Cas création, pas d'ancienne version
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
    Créé un auditlog lors d'une création ou mise à jour.
    """
    # Éviter la récursion
    if sender == AuditLog:
        return

    # Vérifier que la table AuditLog existe avant d'y écrire (éviter error 1146)
    if not table_exists("fortunaisk_auditlog"):
        return

    # Log creation
    if created:
        AuditLog.objects.create(
            user=None,  # Pas d'utilisateur défini sans middleware
            action_type="create",
            model=sender.__name__,
            object_id=instance.pk,
            changes=None,  # Pas de changements sur une création
        )
    else:
        # Log update
        old_instance = getattr(instance, "_pre_save_instance", None)
        if not old_instance:
            # Impossible de récupérer l'ancienne instance
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
    """
    Capture l'état de l'instance avant suppression.
    """
    if sender == AuditLog:
        return

    instance._pre_delete_instance = instance


@receiver(post_delete)
def auditlog_post_delete(sender, instance, **kwargs):
    """
    Loggue une suppression.
    """
    if sender == AuditLog:
        return

    # Vérifier la table
    if not table_exists("fortunaisk_auditlog"):
        return

    AuditLog.objects.create(
        user=None,
        action_type="delete",
        model=sender.__name__,
        object_id=instance.pk,
        changes=None,
    )
