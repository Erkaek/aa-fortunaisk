# fortunaisk/forms/lottery_forms.py

# Standard Library
import json
import logging

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# fortunaisk
from fortunaisk.models import Lottery

logger = logging.getLogger(__name__)


class LotteryCreateForm(forms.ModelForm):
    """
    Formulaire pour créer une loterie standard (non automatique).
    """

    winners_distribution = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text=_("Liste des répartitions des gagnants en pourcentages (JSON)."),
    )

    class Meta:
        model = Lottery
        # Exclusion des champs gérés automatiquement
        exclude = ["start_date", "end_date", "status", "total_pot"]
        widgets = {
            "ticket_price": forms.NumberInput(
                attrs={
                    "step": "1",  # Utilisation de pas de 1 pour des entiers
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
                    "placeholder": _("Illimité si laissé vide"),
                }
            ),
            "payment_receiver": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 1)

        if not distribution_str:
            raise ValidationError(_("La répartition des gagnants est requise."))

        try:
            distribution_list = json.loads(distribution_str)
            if not isinstance(distribution_list, list):
                raise ValueError
            distribution_list = [int(x) for x in distribution_list]
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValidationError(
                _(
                    "Veuillez entrer des pourcentages valides en tant que liste JSON d'entiers."
                )
            )

        if len(distribution_list) != winner_count:
            raise ValidationError(
                _("La répartition doit correspondre au nombre de gagnants.")
            )

        total = sum(distribution_list)
        if total != 100:
            raise ValidationError(_("La somme des pourcentages doit être égale à 100."))

        # Ajout de logs pour débogage
        logger.debug(f"Répartition des gagnants nettoyée: {distribution_list}")

        return distribution_list

    def clean_max_tickets_per_user(self):
        max_tickets = self.cleaned_data.get("max_tickets_per_user")
        if max_tickets == 0:
            return None  # Illimité
        return max_tickets

    def clean(self):
        cleaned_data = super().clean()
        # Add any additional cleaning if necessary
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Gérer max_tickets_per_user
        if instance.max_tickets_per_user == 0:
            instance.max_tickets_per_user = None

        # S'assurer que winners_distribution est une liste de ints
        if isinstance(instance.winners_distribution, str):
            try:
                instance.winners_distribution = json.loads(
                    instance.winners_distribution
                )
            except json.JSONDecodeError:
                raise ValidationError(
                    _("La répartition des gagnants est mal formatée.")
                )

        if commit:
            instance.save()
        return instance
