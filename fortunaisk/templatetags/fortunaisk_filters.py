from django import template
from django.template.defaultfilters import intcomma

register = template.Library()

@register.filter
def space_separated(value):
    if value is None:
        return ''
    return intcomma(value).replace(',', ' ')