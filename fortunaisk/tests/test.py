# fortunaisk/tests.py

from django.test import TestCase
from django.contrib.auth.models import User
from .models import Lottery, AutoLottery, TicketPurchase, Winner, TicketAnomaly
from django.utils import timezone
from unittest.mock import patch
from .tasks import check_purchased_tickets, finalize_lottery

class LotteryModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.lottery = Lottery.objects.create(
            lottery_reference='TESTLOTTERY',
            status='active',
            ticket_price=1000.00,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=1),
            winner_count=1,
            winners_distribution=[100],
            payment_receiver='Test Corp',
            max_tickets_per_user=5,
            duration_value=1,
            duration_unit='days'
        )

    def test_select_winners(self):
        # Create ticket purchases
        TicketPurchase.objects.create(
            lottery=self.lottery,
            user=self.user,
            amount=1000.00,
            payment_id='PAYMENT1',
            status='processed'
        )
        TicketPurchase.objects.create(
            lottery=self.lottery,
            user=self.user,
            amount=1000.00,
            payment_id='PAYMENT2',
            status='processed'
        )
        winners = self.lottery.select_winners()
        self.assertEqual(len(winners), 1)
        self.assertIn(winners[0]['ticket'].payment_id, ['PAYMENT1', 'PAYMENT2'])

class TicketPurchaseTaskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.lottery = Lottery.objects.create(
            lottery_reference='TESTLOTTERY',
            status='active',
            ticket_price=1000.00,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=1),
            winner_count=1,
            winners_distribution=[100],
            payment_receiver='Test Corp',
            max_tickets_per_user=5,
            duration_value=1,
            duration_unit='days'
        )

    @patch('fortunaisk.tasks.CorporationWalletJournalEntry')
    def test_check_purchased_tickets(self, mock_journal_entry):
        # Mock pending payments
        mock_payment = mock_journal_entry.objects.filter.return_value.filter.return_value
        mock_payment.count.return_value = 1
        mock_payment.__iter__.return_value = [
            CorporationWalletJournalEntry(
                id=1,
                reason='TESTLOTTERY',
                amount=1000.00,
                entry_id='PAYMENT1',
                first_party_name_id='CHAR1',
                date=timezone.now(),
                processed=False
            )
        ]

        # Mock related models
        with patch('fortunaisk.tasks.EveCharacter.objects.get') as mock_eve_char, \
             patch('fortunaisk.tasks.CharacterOwnership.objects.get') as mock_char_ownership, \
             patch('fortunaisk.tasks.UserProfile.objects.get') as mock_user_profile:
            mock_eve_char.return_value = type('EveCharacter', (), {'character_id': 'CHAR1', 'character_name': 'TestCharacter'})()
            mock_char_ownership.return_value = type('CharacterOwnership', (), {'user_id': self.user.id})()
            mock_user_profile.return_value = type('UserProfile', (), {'user': self.user, 'main_character_id': 'CHAR1'})()

            check_purchased_tickets()

            # Verify TicketPurchase creation
            self.assertEqual(TicketPurchase.objects.count(), 1)
            ticket = TicketPurchase.objects.first()
            self.assertEqual(ticket.payment_id, 'PAYMENT1')
            self.assertEqual(ticket.status, 'processed')

            # Verify payment is marked as processed
            # Since we're mocking, this part would need more detailed setup

class AutoLotteryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='autotestuser', password='testpass')

    @patch('fortunaisk.tasks.create_lottery_from_auto_lottery.delay')
    def test_create_active_autolottery_creates_lottery(self, mock_create_lottery):
        auto_lottery = AutoLottery.objects.create(
            is_active=True,
            name='AUTO1',
            frequency=1,
            frequency_unit='days',
            ticket_price=1000.00,
            duration_value=1,
            duration_unit='days',
            winner_count=1,
            winners_distribution=[100],
            payment_receiver='Auto Corp',
            max_tickets_per_user=10
        )
        # Simulate saving the AutoLottery
        auto_lottery.save()
        mock_create_lottery.assert_called_once_with(auto_lottery.id)

    @patch('fortunaisk.tasks.create_lottery_from_auto_lottery.delay')
    def test_create_inactive_autolottery_does_not_create_lottery(self, mock_create_lottery):
        auto_lottery = AutoLottery.objects.create(
            is_active=False,
            name='AUTO2',
            frequency=1,
            frequency_unit='days',
            ticket_price=1000.00,
            duration_value=1,
            duration_unit='days',
            winner_count=1,
            winners_distribution=[100],
            payment_receiver='Auto Corp',
            max_tickets_per_user=10
        )
        # Simulate saving the AutoLottery
        auto_lottery.save()
        mock_create_lottery.assert_not_called()

class FormValidationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='formtestuser', password='testpass')

    def test_winners_distribution_sum_to_100(self):
        data = {
            'ticket_price': '1000.00',
            'start_date': '2024-01-01T00:00',
            'end_date': '2024-01-02T00:00',
            'payment_receiver': 'Test Corp',
            'winner_count': 2,
            'winners_distribution': [50, 50],
            'max_tickets_per_user': 5,
            'duration_value': 1,
            'duration_unit': 'days'
        }
        form = LotteryCreateForm(data=data)
        self.assertTrue(form.is_valid())

    def test_winners_distribution_not_sum_to_100(self):
        data = {
            'ticket_price': '1000.00',
            'start_date': '2024-01-01T00:00',
            'end_date': '2024-01-02T00:00',
            'payment_receiver': 'Test Corp',
            'winner_count': 2,
            'winners_distribution': [60, 50],  # Sum is 110
            'max_tickets_per_user': 5,
            'duration_value': 1,
            'duration_unit': 'days'
        }
        form = LotteryCreateForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('winners_distribution', form.errors)
