# fortunaisk/templatetags/fortunaisk_filter.py
"""Custom template filters for FortunaIsk."""

# Django
from django import template
from django.contrib.humanize.templatetags.humanize import intcomma

register = template.Library()


@register.filter
def space_separated(value):
    """
    Format a number with spaces.
    Example: 1000000 -> '1 000 000'
    """
    if value is None:
        return ""
    return intcomma(value).replace(",", " ")
