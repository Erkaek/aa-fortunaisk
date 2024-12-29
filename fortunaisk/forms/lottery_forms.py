# fortunaisk/forms/lottery_forms.py

# Standard Library
import json
import logging

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import Lottery

logger = logging.getLogger(__name__)


class LotteryCreateForm(forms.ModelForm):
    """
    Formulaire pour créer une loterie standard (une seule occurrence).
    """

    winners_distribution = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text=_("Liste des pourcentages de distribution des gagnants (JSON)."),
    )

    payment_receiver = forms.ModelChoiceField(
        queryset=EveCorporationInfo.objects.all(),
        required=False,
        label=_("Récepteur du paiement (Corporation)"),
        help_text=_("Choisissez la corporation qui recevra les paiements."),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Lottery
        # Définir explicitement les champs à inclure
        fields = [
            "ticket_price",
            "duration_value",
            "duration_unit",
            "winner_count",
            "winners_distribution",
            "max_tickets_per_user",
            "payment_receiver",
        ]
        widgets = {
            "ticket_price": forms.NumberInput(
                attrs={
                    "step": "1",
                    "class": "form-control",
                    "placeholder": _("Ex. 100"),
                }
            ),
            "duration_value": forms.NumberInput(
                attrs={
                    "min": "1",
                    "class": "form-control",
                    "placeholder": _("Ex. 7"),
                }
            ),
            "duration_unit": forms.Select(attrs={"class": "form-select"}),
            "winner_count": forms.NumberInput(
                attrs={
                    "min": "1",
                    "class": "form-control",
                    "placeholder": _("Ex. 3"),
                }
            ),
            "max_tickets_per_user": forms.NumberInput(
                attrs={
                    "min": "1",
                    "class": "form-control",
                    "placeholder": _("Laissez vide pour illimité"),
                }
            ),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 1)

        logger.debug(
            "[STANDARD LOTTERY] raw distribution_str=%r, winner_count=%r",
            distribution_str,
            winner_count,
        )

        if not distribution_str:
            raise ValidationError(_("La distribution des gagnants est requise."))

        try:
            distribution_list = json.loads(distribution_str)
            if not isinstance(distribution_list, list):
                raise ValueError
            distribution_list = [int(x) for x in distribution_list]
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValidationError(
                _("Please provide valid percentages as a JSON list of integers.")
            )

        # Vérification de la taille
        if len(distribution_list) != winner_count:
            raise ValidationError(
                _("Distribution does not match the number of winners")
            )

        # Vérification de la somme = 100
        total = sum(distribution_list)
        if total != 100:
            raise ValidationError(_("The sum of the percentages must be 100."))

        logger.debug("[STANDARD LOTTERY] distribution final = %s", distribution_list)
        return distribution_list

    def clean_max_tickets_per_user(self):
        max_tickets = self.cleaned_data.get("max_tickets_per_user")
        if max_tickets == 0:
            return None
        return max_tickets

    def clean(self):
        cleaned_data = super().clean()

        duration_value = cleaned_data.get("duration_value")
        duration_unit = cleaned_data.get("duration_unit")
        if duration_value and duration_unit:
            if duration_unit not in ["hours", "days", "months"]:
                self.add_error("duration_unit", _("Duration must be positive."))
        else:
            self.add_error("duration_value", _("Duration and its unit are required."))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if instance.max_tickets_per_user == 0:
            instance.max_tickets_per_user = None

        # Convertir la distribution en liste d'entiers
        distribution = self.cleaned_data.get("winners_distribution")
        instance.winners_distribution = distribution

        if commit:
            instance.save()
        return instance
