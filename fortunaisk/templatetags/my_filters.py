# fortunaisk/templatetags/my_filters.py

# Django
from django import template

register = template.Library()


@register.filter(name="index")
def index(sequence, position):
    """Returns the item at the given position in the sequence."""
    try:
        return sequence[position]
    except (IndexError, TypeError, ValueError):
        return ""


@register.filter(name="split")
def split(value, delimiter):
    """
    Divise une chaîne de caractères en une liste basée sur le délimiteur donné.
    Usage dans le template: {{ value|split:"," }}
    """
    try:
        return value.split(delimiter)
    except AttributeError:
        return []
