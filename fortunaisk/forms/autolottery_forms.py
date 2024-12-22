# fortunaisk/forms/autolottery_forms.py

# Django
from django import forms
from django.core.exceptions import ValidationError

# fortunaisk
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
            "payment_receiver",
            "max_tickets_per_user",
        ]

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution", "")
        winner_count = self.cleaned_data.get("winner_count", 0)

        # 1) Convertir la chaîne "70,20,10" en [70, 20, 10]
        if isinstance(distribution_str, str):
            try:
                distribution_list = [
                    float(x) for x in distribution_str.split(",") if x.strip()
                ]
            except ValueError:
                raise ValidationError("Please enter valid numbers separated by commas.")
        else:
            raise ValidationError(
                "Please enter a valid comma-separated list of percentages."
            )

        # 2) Vérifications
        if len(distribution_list) != winner_count:
            raise ValidationError(
                "Distribution length does not match number of winners."
            )

        if round(sum(distribution_list), 2) != 100.00:
            raise ValidationError("The sum of distribution must be 100.")

        # Optionnel: Arrondir les valeurs à deux décimales
        distribution_list = [round(x, 2) for x in distribution_list]

        return distribution_list

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
