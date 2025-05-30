# fortunaisk/models/general.py

# Django
from django.db import models


class General(models.Model):
    """
    Dummy model to define application-level permissions.
    """

    class Meta:
        managed = False  # This model won't be created in the database
        default_permissions = ()  # Disable default permissions
        permissions = (  # Define custom permissions
            ("can_access_app", "Can access this app"),
            ("can_admin_app", "Can admin this app"),
        )
