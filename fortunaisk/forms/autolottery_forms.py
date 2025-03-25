# fortunaisk/forms/autolottery_forms.py

# Standard Library
import json
import logging

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import AutoLottery

logger = logging.getLogger(__name__)


class AutoLotteryForm(forms.ModelForm):
    """
    Form to create or edit a recurring (auto) lottery.
    """

    winners_distribution = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
        help_text=_("List of winners' distribution percentages (JSON)."),
    )

    payment_receiver = forms.ModelChoiceField(
        queryset=EveCorporationInfo.objects.all(),
        required=False,
        label=_("Payment Receiver (Corporation)"),
        help_text=_("Choose the corporation that will receive payments."),
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
                attrs={"class": "form-control", "placeholder": _("Lottery name")}
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
                    "step": "1",
                    "class": "form-control",
                    "placeholder": _("Ex. 100"),
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
                    "placeholder": _("Leave blank for unlimited"),
                }
            ),
        }

    def clean_winners_distribution(self):
        distribution_str = self.cleaned_data.get("winners_distribution") or ""
        winner_count = self.cleaned_data.get("winner_count", 1)

        logger.debug(
            "[AUTO LOTTERY] raw distribution_str=%r, winner_count=%r",
            distribution_str,
            winner_count,
        )

        if not distribution_str:
            raise ValidationError(_("The winners distribution is required."))

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
            raise ValidationError(_("The sum of the percentages must be 100."))

        logger.debug("[AUTO LOTTERY] distribution final = %s", distribution_list)
        return distribution_list

    def clean_max_tickets_per_user(self):
        max_tickets = self.cleaned_data.get("max_tickets_per_user")
        if max_tickets == 0:
            return None
        return max_tickets

    def clean(self):
        cleaned_data = super().clean()

        name = cleaned_data.get("name")
        frequency = cleaned_data.get("frequency")
        frequency_unit = cleaned_data.get("frequency_unit")
        duration_value = cleaned_data.get("duration_value")
        duration_unit = cleaned_data.get("duration_unit")

        if not name:
            self.add_error("name", _("Lottery name is required."))

        if frequency and frequency_unit:
            if frequency < 1:
                self.add_error("frequency", _("Frequency must be >= 1."))
        else:
            self.add_error("frequency", _("Frequency and its unit are required."))

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
            self.add_error("duration_value", _("Duration and its unit are required."))

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        if instance.max_tickets_per_user == 0:
            instance.max_tickets_per_user = None

        # ensure the winners_distribution is a list of ints
        if isinstance(instance.winners_distribution, str):
            try:
                instance.winners_distribution = json.loads(
                    instance.winners_distribution
                )
            except json.JSONDecodeError:
                raise ValidationError(_("Invalid JSON distribution format."))

        if commit:
            instance.save()
        return instance
