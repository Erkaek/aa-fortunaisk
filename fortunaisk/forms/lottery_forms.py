# fortunaisk/forms/lottery_forms.py

# Standard Library
import logging
from decimal import Decimal

# Django
from django import forms
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import Lottery

logger = logging.getLogger(__name__)


class LotteryCreateForm(forms.ModelForm):
    """
    Form to create a one-off lottery.
    """

    tax = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        label=_("Tax (%)"),
        help_text=_("Tax percentage applied to each ticket sold."),
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "E.g. 10"}
        ),
    )

    payment_receiver = forms.ModelChoiceField(
        queryset=EveCorporationInfo.objects.all(),
        required=False,
        label=_("Payment Receiver (Corporation)"),
        help_text=_("Choose the corporation that will receive payments."),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Lottery
        fields = [
            "ticket_price",
            "tax",
            "duration_value",
            "duration_unit",
            "winner_count",
            "max_tickets_per_user",
            "payment_receiver",
        ]
        widgets = {
            "ticket_price": forms.NumberInput(
                attrs={
                    "step": "1",
                    "class": "form-control",
                    "placeholder": _("E.g. 100"),
                }
            ),
            "duration_value": forms.NumberInput(
                attrs={"min": "1", "class": "form-control", "placeholder": _("E.g. 7")}
            ),
            "duration_unit": forms.Select(attrs={"class": "form-select"}),
            "winner_count": forms.NumberInput(
                attrs={"min": "1", "class": "form-control", "placeholder": _("E.g. 3")}
            ),
            "max_tickets_per_user": forms.NumberInput(
                attrs={
                    "min": "1",
                    "class": "form-control",
                    "placeholder": _("Leave empty for unlimited"),
                }
            ),
        }

    def clean_max_tickets_per_user(self):
        max_tix = self.cleaned_data.get("max_tickets_per_user")
        return None if max_tix in (0, None) else max_tix

    def clean(self):
        cd = super().clean()
        dv = cd.get("duration_value")
        du = cd.get("duration_unit")
        if not (dv and du in ["hours", "days", "months"]):
            self.add_error(
                "duration_value", _("Duration and unit are required and must be valid.")
            )
        return cd
