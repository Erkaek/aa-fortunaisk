# fortunaisk/forms/autolottery_forms.py

# Standard Library
import logging

# Django
from django import forms  # type: ignore
from django.core.exceptions import ValidationError  # type: ignore

# fortunaisk
from fortunaisk.models import AutoLottery, LotterySettings

logger = logging.getLogger(__name__)


class AutoLotteryForm(forms.ModelForm):
    winners_distribution = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text="List of winner distributions separated by commas.",
    )

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
            "max_tickets_per_user": forms.NumberInput(attrs={"class": "form-control"}),
            "payment_receiver": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 0)

        logger.debug(f"Raw winners_distribution: {distribution_str}")

        if not distribution_str:
            logger.error("winners_distribution est vide.")
            raise ValidationError("La répartition des gagnants est requise.")

        # Convertir la chaîne en liste de floats
        try:
            distribution_list = [
                float(x.strip()) for x in distribution_str.split(",") if x.strip()
            ]
            logger.debug(
                f"Répartition des gagnants après conversion: {distribution_list}"
            )
        except ValueError:
            logger.error("Valeurs non valides dans winners_distribution.")
            raise ValidationError(
                "Veuillez entrer des nombres valides séparés par des virgules."
            )

        # Vérifier que la longueur correspond au nombre de gagnants
        if len(distribution_list) != winner_count:
            logger.error(
                f"Longueur de la répartition ({len(distribution_list)}) ne correspond pas au nombre de gagnants ({winner_count})."
            )
            raise ValidationError(
                "La longueur de la répartition ne correspond pas au nombre de gagnants."
            )

        # Vérifier que la somme des pourcentages est égale à 100
        if round(sum(distribution_list), 2) != 100.00:
            logger.error(
                f"La somme de la répartition est {sum(distribution_list)}, doit être 100."
            )
            raise ValidationError("La somme de la répartition doit être égale à 100.")

        # Optionnel : arrondir chaque valeur à deux décimales
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

        # Set the winners_distribution field
        instance.winners_distribution = self.cleaned_data["winners_distribution"]

        if commit:
            instance.save()
        return instance
