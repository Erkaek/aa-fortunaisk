# fortunaisk/tests/test_forms.py
import pytest
from django.utils import timezone
from fortunaisk.forms import LotteryCreateForm

@pytest.mark.django_db
def test_lottery_create_form_valid():
    form_data = {
        "ticket_price": 100.00,
        "start_date": timezone.now(),
        "end_date": timezone.now() + timezone.timedelta(hours=1),
        "winner_count": 1,
        "winners_distribution": [100],
    }
    form = LotteryCreateForm(data=form_data)
    assert form.is_valid(), form.errors
