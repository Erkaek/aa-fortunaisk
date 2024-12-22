# fortunaisk/tests/test_models.py
# Third Party
import pytest

# Django
from django.contrib.auth.models import User
from django.utils import timezone

# fortunaisk
from fortunaisk.models import Lottery, TicketPurchase


@pytest.mark.django_db
def test_lottery_creation():
    lottery = Lottery.objects.create(
        ticket_price=50.0,
        start_date=timezone.now(),
        end_date=timezone.now() + timezone.timedelta(hours=1),
        payment_receiver=1234,
        lottery_reference="LOTTERY-TEST",
        winner_count=1,
        winners_distribution=[100],
    )
    assert lottery.id is not None


@pytest.mark.django_db
def test_ticket_purchase():
    user = User.objects.create_user("tester", password="testerpass")
    lottery = Lottery.objects.create(
        ticket_price=50.0,
        start_date=timezone.now(),
        end_date=timezone.now() + timezone.timedelta(hours=1),
        payment_receiver=1234,
        lottery_reference="LOTTERY-ABC",
        winner_count=1,
        winners_distribution=[100],
    )
    purchase = TicketPurchase.objects.create(
        user=user,
        lottery=lottery,
        amount=50.0,
    )
    assert purchase.id is not None
