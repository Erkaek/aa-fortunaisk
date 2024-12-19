# fortunaisk/forms.py
"""Forms for the FortunaIsk lottery application."""

# Django
from django import forms

from .models import LotterySettings


class LotterySettingsForm(forms.ModelForm):
    """
    Form for editing the global lottery settings.
    """

    class Meta:
        model = LotterySettings
        fields = ["default_payment_receiver"]
        widgets = {
            "default_payment_receiver": forms.TextInput(attrs={"class": "form-control"})
        }
