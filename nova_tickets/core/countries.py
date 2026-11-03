"""Liste de tous les pays avec indicatif téléphonique (noms en français)."""
import gettext

import phonenumbers
import pycountry

try:
    _fr = gettext.translation("iso3166-1", pycountry.LOCALES_DIR, languages=["fr"])
    _tr = _fr.gettext
except Exception:  # pragma: no cover
    _tr = lambda s: s  # noqa: E731


def _build():
    items = []
    for c in pycountry.countries:
        dial = phonenumbers.country_code_for_region(c.alpha_2)
        if not dial:
            continue
        name = _tr(getattr(c, "common_name", None) or c.name)
        items.append({"code": c.alpha_2, "name": name, "dial": dial})
    items.sort(key=lambda x: x["name"].lower().replace("î", "i").replace("é", "e").replace("ô", "o"))
    return items


COUNTRIES = _build()
COUNTRY_CHOICES = [(c["code"], c["name"]) for c in COUNTRIES]
BY_CODE = {c["code"]: c for c in COUNTRIES}
DIAL_BY_CODE = {c["code"]: c["dial"] for c in COUNTRIES}
DEFAULT_COUNTRY = "BJ"


def country_name(code):
    return BY_CODE.get(code, {}).get("name", code)
