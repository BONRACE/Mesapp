"""Liste de tous les pays : nom FR, drapeau (emoji) et indicatif téléphonique.

Construit dynamiquement avec pycountry + phonenumbers, donc toujours complet.
"""
import gettext
from functools import lru_cache

import phonenumbers
import pycountry

try:
    _fr = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["fr"])
    _tr = _fr.gettext
except Exception:  # pragma: no cover
    _tr = lambda s: s  # noqa: E731


def flag(code: str) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


@lru_cache(maxsize=1)
def all_countries():
    items = []
    for c in pycountry.countries:
        dial = phonenumbers.country_code_for_region(c.alpha_2)
        if not dial:
            continue
        items.append({
            "code": c.alpha_2,
            "name": _tr(c.name),
            "dial": f"+{dial}",
            "flag": flag(c.alpha_2),
        })
    items.sort(key=lambda x: x["name"].lower())
    return items


def country_choices():
    return [(c["code"], f'{c["flag"]} {c["name"]} ({c["dial"]})') for c in all_countries()]


def get_country(code: str):
    for c in all_countries():
        if c["code"] == code:
            return c
    return None


# ------------------------------------------------------------------
# Moyens de paiement par pays (code -> liste). "default" pour les autres.
# ------------------------------------------------------------------
PAYMENT_METHODS = {
    "BJ": ["MTN Mobile Money", "Moov Money", "Celtiis Cash", "Carte bancaire"],
    "CI": ["Orange Money", "MTN Mobile Money", "Moov Money", "Wave", "Carte bancaire"],
    "SN": ["Wave", "Orange Money", "Free Money", "Carte bancaire"],
    "TG": ["T-Money", "Moov Money", "Carte bancaire"],
    "BF": ["Orange Money", "Moov Money", "Carte bancaire"],
    "ML": ["Orange Money", "Moov Money", "Carte bancaire"],
    "NE": ["Airtel Money", "Moov Money", "Carte bancaire"],
    "CM": ["MTN Mobile Money", "Orange Money", "Carte bancaire"],
    "GH": ["MTN MoMo", "Vodafone Cash", "AirtelTigo Money", "Carte bancaire"],
    "NG": ["Virement bancaire", "Carte bancaire", "USSD"],
    "FR": ["Carte bancaire", "PayPal", "Virement SEPA"],
    "BE": ["Carte bancaire", "PayPal", "Virement SEPA"],
    "CA": ["Carte bancaire", "PayPal", "Interac"],
    "US": ["Carte bancaire", "PayPal", "Apple Pay"],
    "default": ["Carte bancaire", "PayPal"],
}


def payment_methods_for(code: str):
    return PAYMENT_METHODS.get(code, PAYMENT_METHODS["default"])


def withdrawal_methods_for(code: str):
    """Les retraits se font vers des moyens locaux (mobile money en priorité)."""
    return [m for m in payment_methods_for(code) if m != "Carte bancaire"] or ["Virement bancaire"]
