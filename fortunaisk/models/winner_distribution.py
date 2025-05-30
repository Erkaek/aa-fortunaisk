# fortunaisk/models/winner_distribution.py

# Django
from django.db import models


class WinnerDistribution(models.Model):
    lottery_reference = models.CharField(
        max_length=20,
        db_index=True,
        verbose_name="Lottery Reference",
    )
    winner_rank = models.PositiveIntegerField(verbose_name="Winner Rank")
    winner_prize_distribution = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name="Prize Distribution (%)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        db_table = "fortunaisk_winnerdistribution"  # Changé pour correspondre au nom Django standard
        ordering = ["lottery_reference", "winner_rank"]
        default_permissions = ()

    def __str__(self):
        return f"{self.lottery_reference} – Rank {self.winner_rank}: {self.winner_prize_distribution}%"
