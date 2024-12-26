# fortunaisk/models/auditlog.py

# Standard Library
import logging

# Django
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)

User = get_user_model()


class AuditLog(models.Model):
    """
    Model to store audit logs for create, update, and delete actions.
    """

    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="User",
        help_text="The user who performed the action.",
    )
    action_type = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        verbose_name="Action Type",
        help_text="The type of action performed.",
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name="Timestamp",
        help_text="The date and time when the action was performed.",
    )
    model = models.CharField(
        max_length=100,
        verbose_name="Model",
        help_text="The model on which the action was performed.",
    )
    object_id = models.PositiveIntegerField(
        verbose_name="Object ID",
        help_text="The ID of the object on which the action was performed.",
    )
    changes = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Changes",
        help_text="A JSON object detailing the changes made.",
    )

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"{self.get_action_type_display()} - {self.model} ({self.object_id}) by {self.user}"
