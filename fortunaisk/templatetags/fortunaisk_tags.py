# fortunaisk/templatetags/fortunaisk_tags.py

from django import template
from fortunaisk.models import Winner

register = template.Library()


@register.filter
def get_winner(winners, lottery_id):
    try:
        return winners.get(ticket__lottery__id=lottery_id)
    except Winner.DoesNotExist:
        return None
