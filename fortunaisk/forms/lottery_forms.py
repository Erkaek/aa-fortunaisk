# fortunaisk/forms/lottery_forms.py

# Standard Library
from datetime import timedelta

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _

# fortunaisk
from fortunaisk.models import Lottery


class LotteryCreateForm(forms.ModelForm):
    class Meta:
        model = Lottery
        fields = [
            "ticket_price",
            "start_date",
            "end_date",
            "winner_count",
            "winners_distribution",
            "max_tickets_per_user",
        ]
        widgets = {
            "ticket_price": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "class": "form-control",
                    "placeholder": _("Ex. 100.00"),
                }
            ),
            "end_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                }
            ),
            "start_date": forms.DateTimeInput(
                attrs={
                    "type": "datetime-local",
                    "class": "form-control",
                    "value": timezone.now().strftime("%Y-%m-%dT%H:%M"),
                    "readonly": "readonly",
                }
            ),
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
        }

    def __init__(self, *args, **kwargs):
        # Récupérer le paramètre 'is_auto_lottery' si fourni
        self.is_auto_lottery = kwargs.pop("is_auto_lottery", False)
        super().__init__(*args, **kwargs)

        if not self.is_auto_lottery:
            # Exclure les champs 'duration_value' et 'duration_unit'
            self.fields.pop("duration_value", None)
            self.fields.pop("duration_unit", None)

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
                _(
                    "Veuillez entrer des pourcentages valides (séparés par des virgules)."
                )
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
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            if end_date <= start_date:
                self.add_error(
                    "end_date",
                    _("La date de fin doit être postérieure à la date de début."),
                )
                return cleaned_data

            delta = end_date - start_date
            # Attribuer duration_value et duration_unit en fonction de delta
            if self.is_auto_lottery:
                # Si c'est une AutoLottery, les champs sont inclus et requis
                if delta <= timedelta(hours=24):
                    cleaned_data["duration_unit"] = "hours"
                    cleaned_data["duration_value"] = int(delta.total_seconds() // 3600)
                elif delta <= timedelta(days=30):
                    cleaned_data["duration_unit"] = "days"
                    cleaned_data["duration_value"] = delta.days
                else:
                    cleaned_data["duration_unit"] = "months"
                    cleaned_data["duration_value"] = delta.days // 30
            else:
                # Pour une loterie standard, la durée est déterminée par start_date et end_date
                # Pas besoin d'assigner duration_value et duration_unit
                pass
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Générer une référence unique si nécessaire
        if not instance.lottery_reference:
            instance.lottery_reference = Lottery.generate_unique_reference()

        # Gérer max_tickets_per_user
        if instance.max_tickets_per_user == 0:
            instance.max_tickets_per_user = None

        # Attribuer start_date si vide
        if not instance.start_date:
            instance.start_date = timezone.now()

        # Assurer que duration_value et duration_unit sont attribués si c'est une AutoLottery
        if self.is_auto_lottery:
            if not instance.duration_value or not instance.duration_unit:
                if instance.end_date and instance.start_date:
                    delta = instance.end_date - instance.start_date
                    duration_unit = (
                        "hours"
                        if delta <= timedelta(hours=24)
                        else "days" if delta <= timedelta(days=30) else "months"
                    )
                    duration_value = (
                        int(delta.total_seconds() // 3600)
                        if duration_unit == "hours"
                        else delta.days if duration_unit == "days" else delta.days // 30
                    )
                    instance.duration_unit = duration_unit
                    instance.duration_value = duration_value

        if commit:
            instance.save()
        return instance
