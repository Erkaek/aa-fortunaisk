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
        distribution_str = self.cleaned_data.get("winners_distribution", "")
        winner_count = self.cleaned_data.get("winner_count", 0)

        # 1) Convertir la chaîne "70,20,10" en [70, 20, 10]
        if isinstance(distribution_str, str):
            try:
                distribution_list = [
                    float(x) for x in distribution_str.split(",") if x.strip()
                ]
            except ValueError:
                raise ValidationError(
                    "Veuillez entrer des nombres valides séparés par des virgules."
                )
        elif isinstance(distribution_str, list):
            distribution_list = distribution_str
        else:
            raise ValidationError(
                "Veuillez entrer une liste valide de pourcentages séparés par des virgules."
            )

        # 2) Vérifications
        if len(distribution_list) != winner_count:
            raise ValidationError(
                "La longueur de la répartition ne correspond pas au nombre de gagnants."
            )

        if round(sum(distribution_list), 2) != 100.00:
            raise ValidationError("La somme de la répartition doit être égale à 100.")

        # Optionnel: Arrondir les valeurs à deux décimales
        distribution_list = [round(x, 2) for x in distribution_list]

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
