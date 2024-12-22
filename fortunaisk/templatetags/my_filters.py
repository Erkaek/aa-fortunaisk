# fortunaisk/templatetags/my_filters.py

# Django
from django import template

register = template.Library()


@register.filter
def index(sequence, position):
    """Returns the item at the given position in the sequence."""
    try:
        return sequence[position]
    except (IndexError, TypeError, ValueError):
        return ""
