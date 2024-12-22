# fortunaisk/tests/test_tasks.py
import pytest
from django.utils import timezone
from fortunaisk.models import Lottery
from fortunaisk.tasks import check_lotteries

@pytest.mark.django_db
def test_check_lotteries():
    # create an active lottery that ended yesterday
    lottery = Lottery.objects.create(
        ticket_price=10.0,
        start_date=timezone.now() - timezone.timedelta(days=2),
        end_date=timezone.now() - timezone.timedelta(days=1),
        payment_receiver=123,
        winner_count=1,
        winners_distribution=[100],
        lottery_reference="LOTTERY-ENDED",
    )
    # run the task
    result = check_lotteries()
    # reload the lottery
    lottery.refresh_from_db()
    assert lottery.status == "completed"
    assert "Checked 1 lotteries." in result
