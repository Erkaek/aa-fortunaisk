# tasks.py
from celery import shared_task
from corptools.models import CorporationWalletJournalEntry
from .app_settings import PAYMENT_CORP
from .models import Ticket

@shared_task
def check_ticket_payments():
    tickets = Ticket.objects.filter(paid=False)
    for ticket in tickets:
        payment = CorporationWalletJournalEntry.objects.filter(
            division__corporation__corporation_id=PAYMENT_CORP,
            reason=ticket.ticket_ref,
            amount__gte=ticket.amount,
        ).first()
        if payment:
            ticket.paid = True
            ticket.payment = payment
            ticket.save()
