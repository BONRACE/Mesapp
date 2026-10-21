"""Moyens de paiement proposés selon le pays (code ISO du pays de l'utilisateur)."""

LABELS = {
    "mtn_momo": "MTN MoMo",
    "moov_money": "Moov Money",
    "celtiis_cash": "Celtiis Cash",
    "orange_money": "Orange Money",
    "wave": "Wave",
    "free_money": "Free Money",
    "tmoney": "T-Money",
    "airtel_money": "Airtel Money",
    "vodafone_cash": "Telecel Cash",
    "airteltigo_money": "AirtelTigo Money",
    "card": "Carte bancaire",
    "bank_transfer": "Virement bancaire",
    "free": "Gratuit",
}

# Mobile money par pays. La carte bancaire est ajoutée en option pour les paiements.
MOBILE_BY_COUNTRY = {
    "BJ": ["mtn_momo", "moov_money", "celtiis_cash"],
    "CI": ["orange_money", "mtn_momo", "moov_money", "wave"],
    "SN": ["wave", "orange_money", "free_money"],
    "TG": ["tmoney", "moov_money"],
    "BF": ["orange_money", "moov_money"],
    "ML": ["orange_money", "moov_money"],
    "NE": ["airtel_money", "orange_money", "moov_money"],
    "GH": ["mtn_momo", "vodafone_cash", "airteltigo_money"],
    "CM": ["mtn_momo", "orange_money"],
    "GN": ["orange_money", "mtn_momo"],
}


def method_label(code: str) -> str:
    return LABELS.get(code, code)


def payment_methods(country: str):
    """Moyens proposés à l'achat : mobile money du pays + carte bancaire (option)."""
    codes = MOBILE_BY_COUNTRY.get(country, []) + ["card"]
    return [(c, LABELS[c]) for c in codes]


def payout_methods(country: str):
    """Moyens de retrait : mobile money local, sinon virement bancaire."""
    codes = MOBILE_BY_COUNTRY.get(country) or ["bank_transfer"]
    return [(c, LABELS[c]) for c in codes]
