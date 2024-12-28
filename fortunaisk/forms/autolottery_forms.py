# fortunaisk/forms/autolottery_forms.py

# Standard Library
import logging

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


class AutoLotteryForm(forms.ModelForm):
    """
    Formulaire pour créer ou éditer une AutoLottery (loterie récurrente).
    """

    winners_distribution = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text=_("Liste des répartitions des gagnants séparées par des virgules."),
    )

    payment_receiver = forms.ModelChoiceField(
        queryset=EveCorporationInfo.objects.all(),
        required=False,
        label=_("Receveur du Paiement (Corporation)"),
        help_text=_("Choisissez la corporation qui recevra les paiements."),
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
            "winner_count",
            "winners_distribution",
            "max_tickets_per_user",
            "payment_receiver",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": _("Nom de la loterie")}
            ),
            "frequency": forms.NumberInput(
                attrs={
                    "min": "1",
                    "class": "form-control",
                    "placeholder": _("Ex. 7"),
                }
            ),
            "frequency_unit": forms.Select(attrs={"class": "form-select"}),
            "ticket_price": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "class": "form-control",
                    "placeholder": _("Ex. 100.00"),
                }
            ),
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
                    "placeholder": _("Illimité si laissé vide"),
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 1)

        logger.debug(f"Répartition des gagnants brute : {distribution_str}")

        if not distribution_str:
            logger.error("winners_distribution est vide.")
            raise ValidationError(_("La répartition des gagnants est requise."))

        try:
            distribution_list = [
                float(x.strip()) for x in distribution_str.split(",") if x.strip()
            ]
            logger.debug(f"Répartition des gagnants : {distribution_list}")
        except ValueError:
            logger.error("Valeurs non valides dans winners_distribution.")
            raise ValidationError(
                _("Veuillez entrer des pourcentages valides séparés par des virgules.")
            )

        if len(distribution_list) != winner_count:
            logger.error(
                f"Longueur de la répartition ({len(distribution_list)}) != {winner_count}"
            )
            raise ValidationError(
                _("La répartition doit correspondre au nombre de gagnants.")
            )

        total = sum(distribution_list)
        if abs(total - 100.0) > 0.001:
            logger.error(f"La somme de la répartition est {total}, doit être ~100.")
            raise ValidationError(
                _("La somme de la répartition doit être égale à 100.")
            )

        # Arrondir chaque valeur à deux décimales
        distribution_list = [round(x, 2) for x in distribution_list]

        return distribution_list

    def clean_max_tickets_per_user(self):
        max_tickets = self.cleaned_data.get("max_tickets_per_user")
        if max_tickets == 0:
            return None  # Illimité
        return max_tickets

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Si max_tickets_per_user < 1 => forçons à 1
        # ou si c'est None, alors c'est illimité => on ne touche pas
        if instance.max_tickets_per_user and instance.max_tickets_per_user < 1:
            instance.max_tickets_per_user = 1

        instance.winners_distribution = self.cleaned_data["winners_distribution"]

        if commit:
            instance.save()
        return instance
