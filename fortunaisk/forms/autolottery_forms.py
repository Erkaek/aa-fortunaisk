# fortunaisk/forms/autolottery_forms.py

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

# fortunaisk
from fortunaisk.models import AutoLottery, Lottery, LotterySettings  # Removed Lottery


class AutoLotteryForm(forms.ModelForm):
    class Meta:
        model = AutoLottery
        fields = [
            "name",
            "frequency",
            "frequency_unit",
            "ticket_price",
            "duration_value",
            "duration_unit",
            "winner_count",
            "winners_distribution",
            "max_tickets_per_user",
            "payment_receiver",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "frequency": forms.NumberInput(attrs={"class": "form-control"}),
            "frequency_unit": forms.Select(attrs={"class": "form-select"}),
            "ticket_price": forms.NumberInput(
                attrs={"step": "0.01", "class": "form-control"}
            ),
            "duration_value": forms.NumberInput(attrs={"class": "form-control"}),
            "duration_unit": forms.Select(attrs={"class": "form-select"}),
            "winner_count": forms.NumberInput(attrs={"class": "form-control"}),
            "winners_distribution": forms.TextInput(attrs={"class": "form-control"}),
            "max_tickets_per_user": forms.NumberInput(attrs={"class": "form-control"}),
            "payment_receiver": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 0)

        if not distribution_str:
            raise ValidationError("La répartition des gagnants est requise.")

        # Convert string separated by commas to a list of floats
        try:
            distribution_list = [
                float(x.strip()) for x in distribution_str.split(",") if x.strip()
            ]
        except ValueError:
            raise ValidationError(
                "Veuillez entrer des nombres valides séparés par des virgules."
            )

        # Check length matches winner_count
        if len(distribution_list) != winner_count:
            raise ValidationError(
                "La longueur de la répartition ne correspond pas au nombre de gagnants."
            )

        # Check sum equals 100
        if round(sum(distribution_list), 2) != 100.00:
            raise ValidationError("La somme de la répartition doit être égale à 100.")

        # Optionally: round each value to two decimals
        distribution_list = [round(x, 2) for x in distribution_list]

        return distribution_list

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Auto-assign the payment receiver from settings if not specified
        if not instance.payment_receiver:
            lottery_settings = LotterySettings.objects.first()
            if lottery_settings:
                instance.payment_receiver = lottery_settings.default_payment_receiver

        # If max tickets is not specified, default to 1
        if instance.max_tickets_per_user is None or instance.max_tickets_per_user < 1:
            instance.max_tickets_per_user = 1

        if commit:
            instance.save()
        return instance
