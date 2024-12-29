# Standard Library
import json
import logging

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _

# fortunaisk
from fortunaisk.models import Lottery

logger = logging.getLogger(__name__)


class LotteryCreateForm(forms.ModelForm):
    """
    Form to create a one-time (standard) lottery.
    """

    winners_distribution = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text=_("List of winners distribution percentages (JSON)."),
    )

    class Meta:
        model = Lottery
        # Exclude fields managed automatically
        exclude = ["start_date", "end_date", "status", "total_pot"]
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
                    "placeholder": _("Leave blank for unlimited"),
                }
            ),
            "payment_receiver": forms.Select(attrs={"class": "form-select"}),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 1)

        if not distribution_str:
            raise ValidationError(_("Winners distribution is required."))

        try:
            distribution_list = json.loads(distribution_str)
            if not isinstance(distribution_list, list):
                raise ValueError
            distribution_list = [int(x) for x in distribution_list]
        except (ValueError, TypeError, json.JSONDecodeError):
            raise ValidationError(
                _("Please provide valid percentages as a JSON list of integers.")
            )

        if len(distribution_list) != winner_count:
            raise ValidationError(
                _("Distribution does not match the number of winners.")
            )

        total = sum(distribution_list)
        if total != 100:
            raise ValidationError(_("Sum of percentages must be 100."))

        logger.debug(f"Lottery standard distribution cleaned: {distribution_list}")
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
            if duration_unit == "hours":
                delta = timezone.timedelta(hours=duration_value)
            elif duration_unit == "days":
                delta = timezone.timedelta(days=duration_value)
            elif duration_unit == "months":
                delta = timezone.timedelta(days=30 * duration_value)
            else:
                delta = timezone.timedelta()

            if delta <= timezone.timedelta():
                self.add_error("duration_value", _("Duration must be positive."))
        else:
            self.add_error("duration_value", _("Duration and unit are required."))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if instance.max_tickets_per_user == 0:
            instance.max_tickets_per_user = None

        instance.winners_distribution = self.cleaned_data.get("winners_distribution")

        if commit:
            instance.save()
        return instance
