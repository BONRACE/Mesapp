from django import template
from django.conf import settings

from core.countries import BY_CODE

register = template.Library()


@register.filter
def money(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return value
    return f"{n:,}".replace(",", " ") + f" {settings.CURRENCY}"


@register.filter
def country_name(code):
    return BY_CODE.get(code, {}).get("name", code)


@register.filter
def dial(code):
    return BY_CODE.get(code, {}).get("dial", "")


@register.filter
def lower(code):
    return str(code).lower()


@register.filter
def percent(part, whole):
    try:
        return min(100, round(int(part) * 100 / int(whole)))
    except (TypeError, ValueError, ZeroDivisionError):
        return 0
