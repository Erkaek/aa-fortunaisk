# fortunaisk/forms/lottery_forms.py

# Standard Library
import logging
from decimal import Decimal

# Third Party
# Corp Tools
from corptools.models import CorporationWalletJournalEntry

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Récupérer les corporations avec accès wallet
        available_corps = EveCorporationInfo.objects.filter(
            corporation_id__in=CorporationWalletJournalEntry.objects.filter(
                second_party_name_id__isnull=False
            )
            .values_list("second_party_name_id", flat=True)
            .distinct()
        )

        if available_corps.exists():
            self.fields["payment_receiver"].queryset = available_corps
            self.fields["payment_receiver"].help_text = _(
                "Choose the corporation that will receive payments (only corporations with wallet access)."
            )
        else:
            # Aucune corporation disponible
            self.fields["payment_receiver"].queryset = EveCorporationInfo.objects.none()
            self.fields["payment_receiver"].help_text = _(
                "No corporations available. Please add your corporation token on CorpTools first."
            )
            self.fields["payment_receiver"].widget.attrs["disabled"] = True

    payment_receiver = forms.ModelChoiceField(
        queryset=EveCorporationInfo.objects.none(),  # Sera redéfini dans __init__
        required=False,
        label=_("Payment Receiver (Corporation)"),
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

    def clean_payment_receiver(self):
        payment_receiver = self.cleaned_data.get("payment_receiver")

        # Vérifier qu'une corporation est sélectionnée
        if not payment_receiver:
            available_corps = EveCorporationInfo.objects.filter(
                corporation_id__in=CorporationWalletJournalEntry.objects.filter(
                    second_party_name_id__isnull=False
                )
                .values_list("second_party_name_id", flat=True)
                .distinct()
            )

            if not available_corps.exists():
                raise forms.ValidationError(
                    _(
                        "No corporations available. Please add your corporation token on CorpTools first."
                    )
                )
            else:
                raise forms.ValidationError(
                    _("Please select a corporation to receive payments.")
                )

        return payment_receiver

    def clean(self):
        cd = super().clean()
        dv = cd.get("duration_value")
        du = cd.get("duration_unit")
        if not (dv and du in ["hours", "days", "months"]):
            self.add_error(
                "duration_value", _("Duration and unit are required and must be valid.")
            )
        return cd
