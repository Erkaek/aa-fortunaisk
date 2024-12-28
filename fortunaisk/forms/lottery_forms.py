# fortunaisk/forms/lottery_forms.py

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _

# fortunaisk
from fortunaisk.models import Lottery


class LotteryCreateForm(forms.ModelForm):
    """
    Formulaire pour créer une loterie standard (non automatique).
    """

    class Meta:
        model = Lottery
        # Exclusion du champ 'start_date'
        exclude = ["start_date"]
        widgets = {
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
            "winners_distribution": forms.HiddenInput(),
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
        distribution = self.cleaned_data.get("winners_distribution", "")
        winner_count = self.cleaned_data.get("winner_count", 1)

        if not distribution:
            raise ValidationError(_("La répartition des gagnants est requise."))

        try:
            distribution_list = [
                float(x.strip()) for x in distribution.split(",") if x.strip()
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
        duration_value = cleaned_data.get("duration_value")
        duration_unit = cleaned_data.get("duration_unit")

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

            end_date = timezone.now() + delta
            if end_date <= timezone.now():
                self.add_error("duration_value", _("La durée doit être positive."))
        else:
            self.add_error("duration_value", _("La durée est requise."))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Générer une référence unique si nécessaire
        if not instance.lottery_reference:
            instance.lottery_reference = Lottery.generate_unique_reference()

        # Gérer max_tickets_per_user
        if instance.max_tickets_per_user == 0:
            instance.max_tickets_per_user = None

        # Définir start_date automatiquement
        instance.start_date = timezone.now()

        if commit:
            instance.save()
        return instance
