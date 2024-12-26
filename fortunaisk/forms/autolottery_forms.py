# fortunaisk/forms/autolottery_forms.py

# Standard Library
import logging

# Django
from django import forms
from django.core.exceptions import ValidationError

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


class AutoLotteryForm(forms.ModelForm):
    """
    Form to create or edit an AutoLottery (recurring lottery).
    """

    winners_distribution = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text="List of winner distributions separated by commas.",
    )

    # ModelChoiceField => liste déroulante de corporations
    payment_receiver = forms.ModelChoiceField(
        queryset=EveCorporationInfo.objects.all(),
        required=False,
        label="Payment Receiver (Corporation)",
        help_text="Choisissez la corporation qui recevra les paiements.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

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
            "max_tickets_per_user",
            "payment_receiver",
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
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 0)

        logger.debug(f"Raw winners_distribution: {distribution_str}")

        if not distribution_str:
            logger.error("winners_distribution est vide.")
            raise ValidationError("La répartition des gagnants est requise.")

        try:
            distribution_list = [
                float(x.strip()) for x in distribution_str.split(",") if x.strip()
            ]
            logger.debug(f"Répartition des gagnants: {distribution_list}")
        except ValueError:
            logger.error("Valeurs non valides dans winners_distribution.")
            raise ValidationError(
                "Veuillez entrer des nombres valides séparés par des virgules."
            )

        if len(distribution_list) != winner_count:
            logger.error(
                f"Longueur de la répartition ({len(distribution_list)}) != {winner_count}"
            )
            raise ValidationError(
                "La longueur de la répartition ne correspond pas au nombre de gagnants."
            )

        total = sum(distribution_list)
        if abs(total - 100.0) > 0.001:
            logger.error(f"La somme de la répartition est {total}, doit être ~100.")
            raise ValidationError("La somme de la répartition doit être égale à 100.")

        # arrondir chaque valeur à deux décimales
        distribution_list = [round(x, 2) for x in distribution_list]

        return distribution_list

    def save(self, commit=True):
        instance = super().save(commit=False)

        # si max_tickets_per_user < 1 => forçons à 1
        # ou si c'est None, alors c'est illimité => on ne touche pas
        if instance.max_tickets_per_user and instance.max_tickets_per_user < 1:
            instance.max_tickets_per_user = 1

        instance.winners_distribution = self.cleaned_data["winners_distribution"]

        if commit:
            instance.save()
        return instance
