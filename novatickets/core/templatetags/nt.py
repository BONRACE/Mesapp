"""Filtres de gabarit : montants FCFA, téléphones, drapeaux."""
from django import template
from django.utils.html import format_html

from core.countries import format_phone

register = template.Library()


@register.filter
def fcfa(value):
    """12500 → « 12 500 FCFA » (espaces insécables)."""
    try:
        n = int(value or 0)
    except (TypeError, ValueError):
        return value
    return f"{n:,}".replace(",", " ") + " FCFA"


@register.filter
def phone(value):
    return format_phone(value) if value else ""


@register.simple_tag
def flag(code, cls="h-4 w-5 rounded-sm"):
    """Drapeau SVG local (flag-icons) pour un code pays ISO à 2 lettres."""
    return format_html('<span class="fi fi-{} {}" aria-hidden="true"></span>', (code or "").lower(), cls)


@register.filter
def get_item(mapping, key):
    return mapping.get(key)


@register.simple_tag(takes_context=True)
def active(context, *url_names):
    """Renvoie « nt-nav-link-active » si l'URL courante correspond."""
    match = getattr(context["request"], "resolver_match", None)
    if match and (match.view_name in url_names or match.url_name in url_names):
        return "nt-nav-link-active"
    return ""
