# fortunaisk/forms.py

# Django
from django import forms

from .models import AutoLottery, Lottery, LotterySettings


class LotterySettingsForm(forms.ModelForm):
    """
    Formulaire pour gérer les paramètres globaux de la loterie.
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
            "default_payment_receiver": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
            "discord_webhook": forms.URLInput(attrs={"class": "form-control"}),
            "default_lottery_duration_value": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
            "default_lottery_duration_unit": forms.Select(
                choices=AutoLottery.DURATION_UNITS,
                attrs={"class": "form-select"},
            ),
            "default_max_tickets_per_user": forms.NumberInput(
                attrs={"class": "form-control", "readonly": "readonly"}
            ),
        }


class LotteryCreateForm(forms.ModelForm):
    """
    Formulaire pour créer une nouvelle loterie.
    """

    class Meta:
        model = Lottery
        fields = [
            "ticket_price",
            "end_date",
            "winner_count",
            "winners_distribution_str",
            "max_tickets_per_user",
            "duration_value",
            "duration_unit",
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
            "winner_count": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Number of winners",
                    "min": "1",
                }
            ),
            "winners_distribution_str": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g., 50,30,20"}
            ),
            "max_tickets_per_user": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Maximum tickets per user",
                    "readonly": "readonly",
                }
            ),
            "duration_value": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter duration value",
                    "min": "1",
                }
            ),
            "duration_unit": forms.Select(
                choices=AutoLottery.DURATION_UNITS,
                attrs={"class": "form-select"},
            ),
        }
        help_texts = {
            "winners_distribution_str": "Ex: '50,30,20' pour 3 gagnants. La somme doit faire 100.",
        }

    def clean_winners_distribution_str(self):
        distribution = self.cleaned_data.get("winners_distribution_str", "")
        try:
            percentages = [int(p.strip()) for p in distribution.split(",")]
            if sum(percentages) != 100:
                raise forms.ValidationError(
                    "La somme des pourcentages doit être égale à 100."
                )
        except ValueError:
            raise forms.ValidationError(
                "Veuillez entrer des pourcentages valides séparés par des virgules."
            )
        return distribution

    def save(self, commit=True):
        instance = super().save(commit=False)
        lottery_settings = LotterySettings.objects.first()
        if lottery_settings:
            instance.payment_receiver = lottery_settings.default_payment_receiver
        if not instance.lottery_reference:
            instance.lottery_reference = Lottery.generate_unique_reference()
        # Max Tickets Per User is set to 1 automatically
        instance.max_tickets_per_user = 1
        if commit:
            instance.save()
        return instance


class AutoLotteryForm(forms.ModelForm):
    """
    Formulaire pour créer ou éditer une loterie automatique.
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
            "winners_distribution_str",
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
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter frequency number",
                    "min": "1",
                }
            ),
            "frequency_unit": forms.Select(attrs={"class": "form-select"}),
            "ticket_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "duration_value": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Duration value",
                    "min": "1",
                }
            ),
            "duration_unit": forms.Select(
                choices=AutoLottery.DURATION_UNITS,
                attrs={"class": "form-select"},
            ),
            "winner_count": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Number of winners",
                    "min": "1",
                }
            ),
            "winners_distribution_str": forms.TextInput(
                attrs={"class": "form-control"}
            ),
        }
        help_texts = {
            "winners_distribution_str": "Ex: '50,30,20' pour 3 gagnants. La somme doit faire 100.",
        }

    def clean_winners_distribution_str(self):
        distribution = self.cleaned_data.get("winners_distribution_str", "")
        try:
            percentages = [int(p.strip()) for p in distribution.split(",")]
            if sum(percentages) != 100:
                raise forms.ValidationError(
                    "La somme des pourcentages doit être égale à 100."
                )
        except ValueError:
            raise forms.ValidationError(
                "Veuillez entrer des pourcentages valides séparés par des virgules."
            )
        return distribution

    def save(self, commit=True):
        instance = super().save(commit=False)
        lottery_settings = LotterySettings.objects.first()
        if lottery_settings:
            instance.payment_receiver = lottery_settings.default_payment_receiver
        # Max Tickets Per User is set to 1 automatically
        instance.max_tickets_per_user = 1
        if commit:
            instance.save()
        return instance
