"""Custom template tags for FortunaIsk."""

# Django
from django import template

# fortunaisk
from fortunaisk.models import Winner

register = template.Library()


@register.filter
def get_winner(winners, lottery_id):
    """
    Returns the winner object for a given lottery_id from the passed queryset of winners.
    If no winner is found, returns None.
    """
    try:
        return winners.get(ticket__lottery__id=lottery_id)
    except Winner.DoesNotExist:
        return None
