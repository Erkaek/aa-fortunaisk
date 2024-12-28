# fortunaisk/forms/lottery_forms.py

# Standard Library
from datetime import timedelta

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

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
            "duration_value",
            "duration_unit",
        ]
        widgets = {
            "ticket_price": forms.NumberInput(attrs={"step": "0.01"}),
            "end_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "duration_unit": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre duration_value et duration_unit non requis
        self.fields["duration_value"].required = False
        self.fields["duration_unit"].required = False

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

        # Vérifier la correspondance du nombre de gagnants
        if len(distribution_list) != winner_count:
            raise ValidationError(
                "La répartition doit correspondre au nombre de gagnants."
            )

        # Vérifier que la somme est égale à 100
        total = sum(distribution_list)
        if abs(total - 100.0) > 0.001:
            raise ValidationError("La somme des pourcentages doit être égale à 100.")

        return distribution_list

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date:
            delta = end_date - start_date
            # Attribuer duration_value et duration_unit en fonction de delta
            if delta <= timedelta(hours=24):
                cleaned_data["duration_unit"] = "hours"
                cleaned_data["duration_value"] = delta.seconds // 3600
            elif delta <= timedelta(days=30):
                cleaned_data["duration_unit"] = "days"
                cleaned_data["duration_value"] = delta.days
            else:
                cleaned_data["duration_unit"] = "months"
                cleaned_data["duration_value"] = delta.days // 30
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

        # Assurer que duration_value et duration_unit sont attribués
        if not instance.duration_value or not instance.duration_unit:
            if instance.end_date and instance.start_date:
                delta = instance.end_date - instance.start_date
                if delta <= timedelta(hours=24):
                    instance.duration_unit = "hours"
                    instance.duration_value = delta.seconds // 3600
                elif delta <= timedelta(days=30):
                    instance.duration_unit = "days"
                    instance.duration_value = delta.days
                else:
                    instance.duration_unit = "months"
                    instance.duration_value = delta.days // 30

        if commit:
            instance.save()
        return instance
