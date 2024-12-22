# fortunaisk/tests/test_views.py
import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from fortunaisk.models import Lottery
from django.utils import timezone


@pytest.mark.django_db
def test_lottery_view(client):
    # Create user
    user = User.objects.create_user(username="testuser", password="pass")
    # Create an active lottery
    Lottery.objects.create(
        ticket_price=50.0,
        start_date=timezone.now(),
        end_date=timezone.now() + timezone.timedelta(days=1),
        payment_receiver=1234,
        lottery_reference="LOTTERY-123",
        winner_count=1,
        winners_distribution=[100],
    )
    # Login
    client.login(username="testuser", password="pass")

    url = reverse("fortunaisk:lottery")
    response = client.get(url)
    assert response.status_code == 200
    assert "LOTTERY-123" in response.content.decode()


@pytest.mark.django_db
def test_user_dashboard_view(client):
    # Create user
    user = User.objects.create_user(username="testuser2", password="pass2")
    client.login(username="testuser2", password="pass2")

    url = reverse("fortunaisk:user_dashboard")
    response = client.get(url)
    assert response.status_code == 200
    assert "My Dashboard" in response.content.decode()
