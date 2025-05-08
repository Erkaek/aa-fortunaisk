# fortunaisk/templatetags/my_filters.py
# Django
from django import template

register = template.Library()


@register.filter(name="index")
def index(sequence, position):
    """
    Returns the item at the given position in the sequence.
    """
    try:
        return sequence[position]
    except (IndexError, TypeError, ValueError):
        return ""


@register.filter(name="split")
def split(value, delimiter):
    """
    Splits a string into a list based on the given delimiter.
    Usage in a template: {{ value|split:"," }}
    """
    try:
        return value.split(delimiter)
    except AttributeError:
        return []


@register.filter
def format_decimal(value):
    """
    Convert a decimal value to a string with a dot as the decimal separator.
    """
    try:
        return str(value).replace(",", ".")
    except (ValueError, TypeError):
        return value  # Return the original value if conversion fails
