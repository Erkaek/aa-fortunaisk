# Django
from django import template

register = template.Library()


@register.filter
def index(sequence, position):
    """
    Retourne sequence[position] si possible, sinon chaîne vide.
    """
    try:
        return sequence[position]
    except (IndexError, TypeError, ValueError):
        return ""
