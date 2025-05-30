# Standard Library
from decimal import Decimal

# Third Party
# Corp Tools
from corptools.models import CorporationWalletJournalEntry

# Django
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

# Alliance Auth
from allianceauth.eveonline.models import EveCorporationInfo

# fortunaisk
from fortunaisk.models import AutoLottery


class AutoLotteryForm(forms.ModelForm):
    # Using JSONField to directly receive a Python list
    winners_distribution = forms.JSONField(
        widget=forms.HiddenInput(),
        required=True,
        help_text=_("JSON list of percentages for each winner (must total 100)."),
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

        # If editing, initialize hidden field with existing list
        if self.instance and self.instance.winners_distribution:
            self.initial["winners_distribution"] = self.instance.winners_distribution
        # If creating, automatically distribute 100%
        elif not self.initial.get("winners_distribution"):
            cnt = int(self.initial.get("winner_count", 1))
            per = 100 // cnt
            arr = [per] * cnt
            arr[-1] = 100 - per * (cnt - 1)
            self.initial["winners_distribution"] = arr

    payment_receiver = forms.ModelChoiceField(
        queryset=EveCorporationInfo.objects.none(),  # Sera redéfini dans __init__
        required=False,
        label=_("Payment Receiver (Corporation)"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = AutoLottery
        fields = [
            "name",
            "frequency",
            "frequency_unit",
            "ticket_price",
            "tax",
            "duration_value",
            "duration_unit",
            "winner_count",
            "winners_distribution",
            "max_tickets_per_user",
            "payment_receiver",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Lottery name"),
                }
            ),
            "frequency": forms.NumberInput(
                attrs={
                    "min": 1,
                    "class": "form-control",
                    "placeholder": _("E.g. 7"),
                }
            ),
            "frequency_unit": forms.Select(attrs={"class": "form-select"}),
            "ticket_price": forms.NumberInput(
                attrs={
                    "step": "1",
                    "class": "form-control",
                    "placeholder": _("E.g. 100"),
                }
            ),
            "tax": forms.NumberInput(
                attrs={
                    "step": "0.01",
                    "class": "form-control",
                    "placeholder": _("E.g. 5"),
                }
            ),
            "duration_value": forms.NumberInput(
                attrs={
                    "min": 1,
                    "class": "form-control",
                    "placeholder": _("E.g. 24"),
                }
            ),
            "duration_unit": forms.Select(attrs={"class": "form-select"}),
            "winner_count": forms.NumberInput(
                attrs={
                    "min": 1,
                    "class": "form-control",
                    "placeholder": _("E.g. 3"),
                }
            ),
            "max_tickets_per_user": forms.NumberInput(
                attrs={
                    "min": 1,
                    "class": "form-control",
                    "placeholder": _("Leave empty for unlimited"),
                }
            ),
        }

    def clean_tax(self):
        tax = self.cleaned_data.get("tax") or Decimal("0.00")
        if not (Decimal("0.00") <= tax <= Decimal("100.00")):
            raise ValidationError(_("Tax percentage must be between 0 and 100."))
        return tax.quantize(Decimal("0.01"))

    def clean_winners_distribution(self):
        data = self.cleaned_data["winners_distribution"]
        # data is already a Python list
        if not isinstance(data, list):
            raise ValidationError(_("Format must be a list."))

        count = self.cleaned_data.get("winner_count", 0)
        if len(data) != count:
            raise ValidationError(
                _("There must be exactly %(count)d values.") % {"count": count}
            )

        dist = []
        for x in data:
            try:
                d = Decimal(str(x))
            except Exception:
                raise ValidationError(_("All percentages must be numeric."))
            if d < 0:
                raise ValidationError(_("All percentages must be ≥ 0."))
            dist.append(d)

        total = sum(dist)
        if total != Decimal("100"):
            raise ValidationError(
                _("The sum of percentages must be exactly 100% (current: %(sum)s %).")
                % {"sum": total}
            )

        # Return raw list (JSONField will store it as is)
        return data

    def clean_max_tickets_per_user(self):
        max_tix = self.cleaned_data.get("max_tickets_per_user")
        return None if max_tix in (None, 0) else max_tix

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
                raise ValidationError(
                    _(
                        "No corporations available. Please add your corporation token on CorpTools first."
                    )
                )
            else:
                raise ValidationError(
                    _("Please select a corporation to receive payments.")
                )

        return payment_receiver

    def clean(self):
        cd = super().clean()
        if not cd.get("name"):
            self.add_error("name", _("Name is required."))
        if cd.get("frequency", 0) < 1:
            self.add_error("frequency", _("Frequency must be ≥ 1."))
        if cd.get("duration_value", 0) < 1:
            self.add_error("duration_value", _("Duration must be ≥ 1."))
        if cd.get("duration_unit") not in dict(self.Meta.model.DURATION_UNITS):
            self.add_error("duration_unit", _("Invalid duration unit."))
        return cd

    def save(self, commit=True):
        inst = super().save(commit=False)
        # normalization
        if inst.max_tickets_per_user in (0, None):
            inst.max_tickets_per_user = None
        if commit:
            inst.save()
        return inst
