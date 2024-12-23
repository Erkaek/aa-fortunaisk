# fortunaisk/forms/lottery_forms.py

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

# fortunaisk
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
            "end_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_winners_distribution(self):
        distribution = self.cleaned_data.get("winners_distribution", "")
        winner_count = self.cleaned_data.get("winner_count", 0)

        if not distribution:
            raise ValidationError("La répartition des gagnants est requise.")

        # Convertir en liste si possible
        try:
            if isinstance(distribution, str):
                distribution_list = [float(x.strip()) for x in distribution.split(",")]
            elif isinstance(distribution, list):
                distribution_list = [float(x) for x in distribution]
            else:
                raise ValueError
        except ValueError:
            raise ValidationError(
                "Veuillez entrer des pourcentages valides (séparés par des virgules)."
            )

        # Vérifier la correspondance avec le nombre de gagnants
        if len(distribution_list) != winner_count:
            raise ValidationError(
                "La répartition doit correspondre au nombre de gagnants."
            )

        # Vérifier que la somme des pourcentages est 100
        if round(sum(distribution_list), 2) != 100.0:
            raise ValidationError("La somme des pourcentages doit être égale à 100.")

        return distribution_list

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
        if instance.max_tickets_per_user is None or instance.max_tickets_per_user < 1:
            instance.max_tickets_per_user = 1

        # Force the start_date if blank
        if not instance.start_date:
            instance.start_date = timezone.now()

        if commit:
            instance.save()
        return instance
