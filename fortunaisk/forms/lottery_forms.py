# fortunaisk/forms/lottery_forms.py
from typing import List

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from fortunaisk.models import Lottery, LotterySettings


class LotteryCreateForm(forms.ModelForm):
    """
    Form for creating a new one-time Lottery.
    """

    class Meta:
        model = Lottery
        fields = [
            "ticket_price",
            "start_date",
            "end_date",
            "winner_count",
            "winners_distribution",
            "max_tickets_per_user",
            "duration_value",
            "duration_unit",
        ]
        widgets = {
            "ticket_price": forms.NumberInput(attrs={"step": "0.01"}),
            "end_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
            "start_date": forms.DateTimeInput(
                attrs={"type": "datetime-local"}
            ),
        }

    def clean(self) -> dict:
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError("End date must be strictly after start date.")

        # check distribution
        distribution = cleaned_data.get("winners_distribution", [])
        winner_count = cleaned_data.get("winner_count", 0)
        if not isinstance(distribution, list):
            raise ValidationError("Winners distribution must be a list.")
        if len(distribution) != winner_count:
            raise ValidationError(
                f"The distribution length ({len(distribution)}) does not match the number of winners ({winner_count})."
            )
        if sum(distribution) != 100:
            raise ValidationError("The sum of the distribution percentages must be 100.")

        return cleaned_data

    def save(self, commit: bool = True) -> Lottery:
        instance = super().save(commit=False)
        # auto-assign payment receiver from settings
        lottery_settings = LotterySettings.objects.first()
        if lottery_settings:
            instance.payment_receiver = lottery_settings.default_payment_receiver

        # If no reference, generate one
        if not instance.lottery_reference:
            instance.lottery_reference = Lottery.generate_unique_reference()

        # If max tickets was not specified, fallback to 1
        if instance.max_tickets_per_user is None:
            instance.max_tickets_per_user = 1

        # Force the start_date if blank
        if not instance.start_date:
            instance.start_date = timezone.now()

        if commit:
            instance.save()
        return instance
