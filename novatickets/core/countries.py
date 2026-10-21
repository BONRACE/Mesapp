"""Liste des pays (noms français, drapeaux, indicatifs) et validation des téléphones."""
import gettext
from functools import lru_cache

import phonenumbers
import pycountry
from django.core.exceptions import ValidationError

_FR = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["fr"], fallback=True)


def flag_emoji(iso2: str) -> str:
    """Drapeau en emoji à partir du code ISO à 2 lettres."""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


@lru_cache(maxsize=1)
def all_countries():
    """Tous les pays disposant d'un indicatif téléphonique, triés par nom français."""
    items = []
    for c in pycountry.countries:
        code = c.alpha_2
        if code not in phonenumbers.SUPPORTED_REGIONS:
            continue
        name = _FR.gettext(getattr(c, "common_name", c.name))
        items.append(
            {
                "code": code,
                "name": name,
                "dial": f"+{phonenumbers.country_code_for_region(code)}",
                "flag": flag_emoji(code),
            }
        )
    items.sort(key=lambda x: x["name"].lower().replace("î", "i").replace("é", "e"))
    return items


def country_choices():
    return [(c["code"], f'{c["flag"]} {c["name"]} ({c["dial"]})') for c in all_countries()]


def country_name(code: str) -> str:
    for c in all_countries():
        if c["code"] == code:
            return c["name"]
    return code


def normalize_phone(raw: str, region: str) -> str:
    """Valide un numéro mobile selon le pays et le renvoie au format E.164.

    Accepte un numéro national (« 01 97 12 34 56 ») ou international (« +229 … »).
    """
    raw = (raw or "").strip()
    if not raw:
        raise ValidationError("Le numéro de téléphone est obligatoire.")
    try:
        number = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        raise ValidationError("Numéro de téléphone invalide.")
    if not phonenumbers.is_valid_number(number):
        raise ValidationError("Ce numéro n'est pas valide pour le pays sélectionné.")
    if phonenumbers.region_code_for_number(number) != region:
        raise ValidationError("L'indicatif du numéro ne correspond pas au pays sélectionné.")
    kind = phonenumbers.number_type(number)
    if kind not in (phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE):
        raise ValidationError("Veuillez saisir un numéro de téléphone mobile.")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def format_phone(e164: str) -> str:
    """Affichage lisible d'un numéro E.164 (« +229 01 97 12 34 56 »)."""
    try:
        return phonenumbers.format_number(phonenumbers.parse(e164), phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except phonenumbers.NumberParseException:
        return e164


def normalize_phone_any(raw: str, default_region: str) -> str:
    """Valide un numéro (mobile ou fixe) de n'importe quel pays, renvoie du E.164.

    Sert pour les bénéficiaires d'un ticket offert : leur pays n'est pas connu,
    on accepte donc un numéro international « +… » ou national du pays par défaut.
    """
    raw = (raw or "").strip()
    try:
        number = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        raise ValidationError("Numéro de téléphone invalide.")
    if not phonenumbers.is_valid_number(number):
        raise ValidationError("Numéro de téléphone invalide.")
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
