# fortunaisk/forms/autolottery_forms.py

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone  # Ajout de l'import manquant
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import AutoLottery


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
            "duration_value": forms.NumberInput(
                attrs={
                    "min": "1",
                    "class": "form-control",
                    "placeholder": _("Ex. 1"),
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
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 1)

        if not distribution_str:
            raise ValidationError(_("La répartition des gagnants est requise."))

        try:
            distribution_list = [
                float(x.strip()) for x in distribution_str.split(",") if x.strip()
            ]
        except ValueError:
            raise ValidationError(
                _("Veuillez entrer des pourcentages valides séparés par des virgules.")
            )

        if len(distribution_list) != winner_count:
            raise ValidationError(
                _("La répartition doit correspondre au nombre de gagnants.")
            )

        total = sum(distribution_list)
        if abs(total - 100.0) > 0.001:
            raise ValidationError(_("La somme des pourcentages doit être égale à 100."))

        # Arrondir chaque valeur à deux décimales
        distribution_list = [round(x, 2) for x in distribution_list]

        return distribution_list

    def clean_max_tickets_per_user(self):
        max_tickets = self.cleaned_data.get("max_tickets_per_user")
        if max_tickets == 0:
            return None  # Illimité
        return max_tickets

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        frequency = cleaned_data.get("frequency")
        frequency_unit = cleaned_data.get("frequency_unit")
        duration_value = cleaned_data.get("duration_value")
        duration_unit = cleaned_data.get("duration_unit")

        if not name:
            self.add_error("name", _("Le nom de la loterie est requis."))

        if frequency and frequency_unit:
            if frequency < 1:
                self.add_error("frequency", _("La fréquence doit être au moins de 1."))
        else:
            self.add_error("frequency", _("La fréquence et son unité sont requises."))

        if duration_value and duration_unit:
            if duration_unit == "hours":
                delta = timezone.timedelta(hours=duration_value)
            elif duration_unit == "days":
                delta = timezone.timedelta(days=duration_value)
            elif duration_unit == "months":
                # Approximation: 1 mois = 30 jours
                delta = timezone.timedelta(days=duration_value * 30)
            else:
                delta = timezone.timedelta()

            if delta <= timezone.timedelta():
                self.add_error("duration_value", _("La durée doit être positive."))
        else:
            self.add_error("duration_value", _("La durée et son unité sont requises."))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Gérer max_tickets_per_user
        if instance.max_tickets_per_user == 0:
            instance.max_tickets_per_user = None

        if commit:
            instance.save()
        return instance
