# fortunaisk/models/reward.py
import logging

from django.db import models

logger = logging.getLogger(__name__)


class Reward(models.Model):
    """
    Represents a reward that users can get based on their points.
    """

    name = models.CharField(
        max_length=100,
        verbose_name="Reward Name"
    )
    description = models.TextField(
        verbose_name="Reward Description"
    )
    points_required = models.PositiveIntegerField(
        verbose_name="Points Required"
    )

    def __str__(self) -> str:
        return self.name
