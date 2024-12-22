# fortunaisk/forms/settings_forms.py
from django import forms

from fortunaisk.models import LotterySettings, AutoLottery


class LotterySettingsForm(forms.ModelForm):
    """
    Form to manage global lottery settings.
    """

    class Meta:
        model = LotterySettings
        fields = [
            "default_payment_receiver",
            "discord_webhook",
            "default_lottery_duration_value",
            "default_lottery_duration_unit",
            "default_max_tickets_per_user",
        ]
        widgets = {
            "default_payment_receiver": forms.NumberInput(attrs={"class": "form-control"}),
            "discord_webhook": forms.URLInput(attrs={"class": "form-control"}),
            "default_lottery_duration_value": forms.NumberInput(attrs={"class": "form-control"}),
            "default_lottery_duration_unit": forms.Select(
                choices=AutoLottery.DURATION_UNITS, attrs={"class": "form-select"},
            ),
            "default_max_tickets_per_user": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
        }
