# fortunaisk/models/user_profile.py
import logging

from django.db import models
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


class UserProfile(models.Model):
    """
    Extends the User model to include points and associated rewards.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Django User"
    )
    points = models.PositiveIntegerField(
        default=0,
        verbose_name="User Points"
    )
    # "Reward" is imported locally to avoid circular import
    def _reward_model():
        from .reward import Reward
        return Reward

    rewards = models.ManyToManyField(
        _reward_model(),
        blank=True,
        related_name="users",
        verbose_name="Rewards"
    )

    def __str__(self) -> str:
        return f"Profile of {self.user.username}"

    def check_rewards(self) -> None:
        """
        Checks if the user is eligible for new rewards and assigns them.
        Also triggers a Discord notification for newly granted rewards.
        """
        from .reward import Reward
        from fortunaisk.notifications import send_discord_notification

        eligible_rewards = Reward.objects.filter(
            points_required__lte=self.points
        ).exclude(id__in=self.rewards.all())

        for reward in eligible_rewards:
            self.rewards.add(reward)
            # Notify user via Discord
            send_discord_notification(
                message=(
                    f"{self.user.username} has earned the reward '{reward.name}'!"
                )
            )
