# fortunaisk/forms/lottery_forms.py

# Standard Library
import json

# Django
from django import forms
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
        # Exclusion du champ 'start_date' car il est géré automatiquement
        exclude = ["start_date"]
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

    def clean(self):
        cleaned_data = super().clean()
        distribution = cleaned_data.get("winners_distribution", [])
        winner_count = cleaned_data.get("winner_count", 1)

        if not distribution:
            self.add_error(
                "winners_distribution", _("La répartition des gagnants est requise.")
            )
            return cleaned_data

        # Parse JSON si c'est une chaîne
        if isinstance(distribution, str):
            try:
                distribution = json.loads(distribution)
            except json.JSONDecodeError:
                self.add_error(
                    "winners_distribution",
                    _("La répartition des gagnants doit être une liste JSON valide."),
                )
                return cleaned_data

        # Si la distribution est un seul int, le convertir en liste
        if isinstance(distribution, (float, int)):
            distribution = [distribution]

        if not isinstance(distribution, list):
            self.add_error(
                "winners_distribution",
                _("La répartition des gagnants doit être une liste de pourcentages."),
            )
            return cleaned_data

        try:
            # Convertir en entiers
            distribution_list = [int(x) for x in distribution]
        except (ValueError, TypeError):
            self.add_error(
                "winners_distribution",
                _("Veuillez entrer des pourcentages valides (entiers)."),
            )
            return cleaned_data

        # Vérifier la correspondance entre la répartition et le nombre de gagnants
        if len(distribution_list) != winner_count:
            self.add_error(
                "winners_distribution",
                _(
                    "La répartition doit correspondre au nombre de gagnants. "
                    f"Nombre de gagnants attendu : {winner_count}, mais répartition reçue : {len(distribution_list)}."
                ),
            )

        # Vérifier que la somme des pourcentages est égale à 100
        total = sum(distribution_list)
        if total != 100:
            self.add_error(
                "winners_distribution",
                _("La somme des pourcentages doit être égale à 100."),
            )

        # Mettre à jour cleaned_data avec la répartition validée
        cleaned_data["winners_distribution"] = distribution_list

        return cleaned_data

    def clean_max_tickets_per_user(self):
        max_tickets = self.cleaned_data.get("max_tickets_per_user")
        if max_tickets == 0:
            return None  # Illimité
        return max_tickets

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
