# fortunaisk/forms/autolottery_forms.py
from typing import List

from django import forms
from django.core.exceptions import ValidationError

from fortunaisk.models import AutoLottery, LotterySettings


class AutoLotteryForm(forms.ModelForm):
    """
    Form for creating or editing an AutoLottery.
    """

    class Meta:
        model = AutoLottery
        fields = [
            "is_active",
            "name",
            "frequency",
            "frequency_unit",
            "ticket_price",
            "duration_value",
            "duration_unit",
            "winner_count",
            "winners_distribution",
        ]

    def clean_winners_distribution(self) -> List[int]:
        distribution = self.cleaned_data.get("winners_distribution", [])
        winner_count = self.cleaned_data.get("winner_count", 0)

        if not isinstance(distribution, list):
            raise ValidationError("Please enter a valid list of percentages.")
        if len(distribution) != winner_count:
            raise ValidationError(
                f"Distribution length ({len(distribution)}) does not match the number of winners ({winner_count})."
            )
        if sum(distribution) != 100:
            raise ValidationError("The sum of percentages must be 100.")
        return distribution

    def save(self, commit: bool = True) -> AutoLottery:
        instance = super().save(commit=False)
        # auto-assign payment receiver from settings
        lottery_settings = LotterySettings.objects.first()
        if lottery_settings:
            instance.payment_receiver = lottery_settings.default_payment_receiver

        # set max tickets to 1 if not set
        if instance.max_tickets_per_user < 1:
            instance.max_tickets_per_user = 1

        if commit:
            instance.save()
        return instance
