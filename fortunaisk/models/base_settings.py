# fortunaisk/models/base_settings.py
import logging

from django.db import models
from solo.models import SingletonModel

logger = logging.getLogger(__name__)


class LotterySettings(SingletonModel):
    """
    Global settings for the FortunaIsk Lottery application.
    """

    default_payment_receiver = models.IntegerField(
        default=0,
        verbose_name="Default Payment Receiver ID",
        help_text="ID of the default payment receiver."
    )
    discord_webhook = models.URLField(
        null=True,
        blank=True,
        verbose_name="Discord Webhook",
        help_text="Optional Discord webhook URL for lottery notifications."
    )
    default_lottery_duration_value = models.PositiveIntegerField(
        default=24,
        verbose_name="Default Duration Value",
        help_text="Default duration (number) for newly created lotteries."
    )
    default_lottery_duration_unit = models.CharField(
        max_length=10,
        choices=[
            ("hours", "Hours"),
            ("days", "Days"),
            ("months", "Months"),
        ],
        default="hours",
        verbose_name="Default Duration Unit",
        help_text="Default unit of time for the lottery duration."
    )
    default_max_tickets_per_user = models.PositiveIntegerField(
        default=1,
        verbose_name="Default Max Tickets per User",
        help_text="Default limit of tickets per user."
    )

    def __str__(self) -> str:
        return "Lottery Settings"

    class Meta:
        verbose_name = "Lottery Settings"
