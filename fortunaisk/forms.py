# Django
from django import forms

from .models import LotterySettings


class LotterySettingsForm(forms.ModelForm):
    class Meta:
        model = LotterySettings
        fields = ["default_payment_receiver"]
        widgets = {
            "default_payment_receiver": forms.TextInput(attrs={"class": "form-control"})
        }
