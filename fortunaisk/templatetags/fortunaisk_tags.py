# fortunaisk/templatetags/fortunaisk_tags.py

# Standard Library
import random

# Django
from django import template

# fortunaisk
from fortunaisk.models import Winner

register = template.Library()


@register.filter
def get_winner(winners, lottery_id):
    try:
        return winners.get(ticket__lottery__id=lottery_id)
    except Winner.DoesNotExist:
        return None


@register.filter
def get_winners(lottery, num_winners=1):
    participants = lottery.ticketpurchase_set.values_list("user", flat=True).distinct()
    if num_winners > participants.count():
        num_winners = participants.count()
    return random.sample(list(participants), num_winners)


@register.simple_tag
def select_winner(lottery):
    participants = list(
        lottery.ticketpurchase_set.values_list("user__username", flat=True)
    )
    if not participants:
        return "Aucun participant"
    return random.choice(participants)
