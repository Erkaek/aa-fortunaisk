# fortunaisk/forms.py

# Django
from django import forms
from django.utils import timezone

from .models import AutoLottery, Lottery, LotterySettings


class LotterySettingsForm(forms.ModelForm):
    """
    Form for managing global lottery settings.
    """

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


class LotteryCreateForm(forms.ModelForm):
    """
    Form for creating a new lottery.
    """

    class Meta:
        model = Lottery
        fields = [
            "ticket_price",
            "end_date",
            "payment_receiver",
            "winner_count",
            "winners_distribution_str",
            "max_tickets_per_user",
        ]
        widgets = {
            "ticket_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "placeholder": "Enter ticket price in ISK",
                }
            ),
            "end_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "placeholder": "Select end date and time",
                }
            ),
            "payment_receiver": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter payment receiver ID",
                }
            ),
            "winner_count": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Number of winners"}
            ),
            "winners_distribution_str": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., 50,30,20"}
            ),
            "max_tickets_per_user": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Maximum tickets per user",
                }
            ),
        }
        help_texts = {
            "winners_distribution_str": "Ex: '50,30,20' pour 3 gagnants. La somme doit faire 100.",
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not instance.start_date:
            instance.start_date = timezone.now()
        if commit:
            instance.save()
        return instance


class AutoLotteryForm(forms.ModelForm):
    """
    Form for creating or editing an automatic lottery.
    """

    class Meta:
        model = AutoLottery
        fields = [
            "is_active",
            "name",
            "frequency",
            "frequency_unit",
            "ticket_price",
            "duration_hours",
            "payment_receiver",
            "winner_count",
            "winners_distribution_str",
            "max_tickets_per_user",
        ]
        widgets = {
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Unique name for the automatic lottery",
                }
            ),
            "frequency": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Enter frequency number"}
            ),
            "frequency_unit": forms.Select(attrs={"class": "form-select"}),
            "ticket_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "duration_hours": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Duration in hours"}
            ),
            "payment_receiver": forms.NumberInput(attrs={"class": "form-control"}),
            "winner_count": forms.NumberInput(attrs={"class": "form-control"}),
            "winners_distribution_str": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "max_tickets_per_user": forms.NumberInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "winners_distribution_str": "Ex: '50,30,20' pour 3 gagnants. La somme doit faire 100.",
        }
