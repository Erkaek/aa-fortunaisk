# fortunaisk/forms.py
# Django
from django import forms
from django.utils import timezone

from .models import Lottery, LotterySettings


class LotterySettingsForm(forms.ModelForm):
    class Meta:
        model = LotterySettings
        fields = [
            "default_payment_receiver",
            "discord_webhook",
            "default_lottery_duration_hours",
            "default_max_tickets_per_user",
        ]
        widgets = {
            "default_payment_receiver": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "discord_webhook": forms.URLInput(attrs={"class": "form-control"}),
            "default_lottery_duration_hours": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
            "default_max_tickets_per_user": forms.NumberInput(
                attrs={"class": "form-control"}
            ),
        }


class LotteryCreateForm(forms.ModelForm):
    class Meta:
        model = Lottery
        fields = [
            "ticket_price",
            "end_date",
            "payment_receiver",
            "winner_count",
            "winners_distribution_str",
            "max_tickets_per_user",
        ]
        widgets = {
            "ticket_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "end_date": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "payment_receiver": forms.NumberInput(attrs={"class": "form-control"}),
            "winner_count": forms.NumberInput(attrs={"class": "form-control"}),
            "winners_distribution_str": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "max_tickets_per_user": forms.NumberInput(attrs={"class": "form-control"}),
        }
        help_texts = {
            "winners_distribution_str": "Ex: '50,30,20' pour 3 gagnants. La somme doit faire 100.",
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Définir start_date si non précisé
        if not instance.start_date:
            instance.start_date = timezone.now()
        # La référence sera générée automatiquement dans le modèle
        if commit:
            instance.save()
        return instance
