# fortunaisk/models/user_profile.py

# Standard Library
import logging

# Django
from django.contrib.auth.models import User
from django.db import models

logger = logging.getLogger(__name__)


class UserProfile(models.Model):
    """
    Extends the User model to include rewards, for FortunaIsk specifically.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="fortunaisk_profile",  # Changed to avoid conflict "profile"
        verbose_name="Django User",
    )
    rewards = models.ManyToManyField(
        "Reward",
        blank=True,
        related_name="users",
        verbose_name="Rewards",
    )

    def __str__(self) -> str:
        return f"FortunaIsk Profile of {self.user.username}"
