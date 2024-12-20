# fortunaisk/forms.py
"""Forms for the FortunaIsk lottery application."""
# Django
from django import forms

from .models import LotterySettings


class LotterySettingsForm(forms.ModelForm):
    class Meta:
        model = LotterySettings
        fields = [
            "default_payment_receiver",
            "discord_webhook",
            "default_lottery_duration_hours",
            "default_max_tickets_per_user",
        ]
        widgets = {
            "default_payment_receiver": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "discord_webhook": forms.URLInput(attrs={"class": "form-control"}),
            "default_lottery_duration_hours": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
            "default_max_tickets_per_user": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
        }
