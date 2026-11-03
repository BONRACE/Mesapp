"""Catalogue des canaux de réception des fonds (retraits organisateur).

Chaque canal indique le type de compte attendu et les pays où il est proposé
(None = disponible partout). Pour ajouter un canal : une ligne ici, rien d'autre.
"""

PHONE, BANK, EMAIL = "phone", "bank", "email"

CHANNELS = {
    "mtn_momo": {"label": "MTN MoMo", "type": PHONE, "countries": {"BJ", "CI", "CM", "GH"}},
    "moov_money": {"label": "Moov Money", "type": PHONE, "countries": {"BJ", "CI", "TG", "BF", "ML", "NE"}},
    "celtiis_cash": {"label": "Celtiis Cash", "type": PHONE, "countries": {"BJ"}},
    "orange_money": {"label": "Orange Money", "type": PHONE, "countries": {"CI", "SN", "BF", "ML", "CM"}},
    "wave": {"label": "Wave", "type": PHONE, "countries": {"SN", "CI"}},
    "tmoney": {"label": "T-Money", "type": PHONE, "countries": {"TG"}},
    "free_money": {"label": "Free Money", "type": PHONE, "countries": {"SN"}},
    "airtel_money": {"label": "Airtel Money", "type": PHONE, "countries": {"NE"}},
    "coris_money": {"label": "Coris Money", "type": PHONE, "countries": {"BF"}},
    "vodafone_cash": {"label": "Vodafone Cash", "type": PHONE, "countries": {"GH"}},
    "airteltigo_money": {"label": "AirtelTigo Money", "type": PHONE, "countries": {"GH"}},
    "opay": {"label": "OPay", "type": PHONE, "countries": {"NG"}},
    "bank": {"label": "Virement bancaire", "type": BANK, "countries": None},
    "paypal": {"label": "PayPal", "type": EMAIL, "countries": None},
}

KIND_CHOICES = [(k, v["label"]) for k, v in CHANNELS.items()]


def channels_for_country(code):
    """Canaux disponibles pour un organisateur installé dans `code` (mobile money du pays + banque + PayPal)."""
    return {k: v for k, v in CHANNELS.items() if v["countries"] is None or code in v["countries"]}
