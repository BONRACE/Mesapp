"""Moyens de paiement par pays + passerelle de paiement SIMULÉE.

Pour passer en production, remplacer le corps de `process_payment` par un appel
à FedaPay / KkiaPay / CinetPay / Stripe, sans toucher au reste du code.
"""
import uuid


def _m(key, label, kind="momo"):
    return {"key": key, "label": label, "kind": kind}


CARD = _m("card", "Carte bancaire (Visa / Mastercard)", "card")
PAYPAL = _m("paypal", "PayPal", "wallet")
BANK = _m("bank", "Virement bancaire", "bank")

BY_COUNTRY = {
    "BJ": [_m("mtn_bj", "MTN MoMo"), _m("moov_bj", "Moov Money"), _m("celtiis_bj", "Celtiis Cash"), CARD],
    "CI": [_m("orange_ci", "Orange Money"), _m("mtn_ci", "MTN MoMo"), _m("moov_ci", "Moov Money"), _m("wave_ci", "Wave"), CARD],
    "SN": [_m("wave_sn", "Wave"), _m("orange_sn", "Orange Money"), _m("free_sn", "Free Money"), CARD],
    "TG": [_m("tmoney_tg", "T-Money"), _m("moov_tg", "Moov Money"), CARD],
    "BF": [_m("orange_bf", "Orange Money"), _m("moov_bf", "Moov Money"), _m("coris_bf", "Coris Money"), CARD],
    "ML": [_m("orange_ml", "Orange Money"), _m("moov_ml", "Moov Money"), CARD],
    "NE": [_m("airtel_ne", "Airtel Money"), _m("moov_ne", "Moov Money"), CARD],
    "CM": [_m("mtn_cm", "MTN MoMo"), _m("orange_cm", "Orange Money"), CARD],
    "GH": [_m("mtn_gh", "MTN MoMo"), _m("vodafone_gh", "Vodafone Cash"), _m("airteltigo_gh", "AirtelTigo Money"), CARD],
    "NG": [_m("opay_ng", "OPay"), _m("bank_ng", "Virement bancaire", "bank"), CARD],
    "FR": [CARD, PAYPAL, _m("sepa", "Virement SEPA", "bank")],
}
DEFAULT = [CARD, PAYPAL]


def methods_for_country(code):
    """Moyens de paiement proposés à un acheteur selon son pays."""
    return BY_COUNTRY.get(code, DEFAULT)


def payout_methods_for_country(code):
    """Moyens de retrait locaux (mobile money, virement, wallet — jamais la carte)."""
    methods = [m for m in methods_for_country(code) if m["kind"] != "card"]
    return methods or [BANK]


def find_method(code, key, payout=False):
    pool = payout_methods_for_country(code) if payout else methods_for_country(code)
    return next((m for m in pool if m["key"] == key), None)


def process_payment(method, phone, amount):
    """Passerelle simulée. Renvoie (ok, référence_fournisseur, message).

    Pour tester un échec : utiliser un numéro finissant par 0000.
    """
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if method["kind"] == "momo" and digits.endswith("0000"):
        return False, "", "Paiement refusé par l'opérateur (solde insuffisant — simulation)."
    return True, f"SIM-{uuid.uuid4().hex[:10].upper()}", "Paiement validé."
