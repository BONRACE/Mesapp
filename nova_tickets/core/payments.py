"""Moyens de paiement par pays + passerelle de paiement SIMULÉE.

Pour passer en production, remplacer le corps de `process_payment` par un appel
à FedaPay / KkiaPay / CinetPay / Stripe, sans toucher au reste du code.
"""
import uuid


def _m(key, label, kind="momo", provider=None):
    """provider ("MTN" | "Moov") : moyen géré par le module payments (push + webhook), zone FCFA (XOF) uniquement :
    Bénin, Côte d'Ivoire, Togo, Burkina, Mali, Niger. MTN Cameroun / Ghana (autres devises) restent simulés.
    Sans provider : paiement encore simulé par process_payment()."""
    return {"key": key, "label": label, "kind": kind, "provider": provider}


CARD = _m("card", "Carte bancaire (Visa / Mastercard)", "card")
PAYPAL = _m("paypal", "PayPal", "wallet")
BANK = _m("bank", "Virement bancaire", "bank")

BY_COUNTRY = {
    "BJ": [_m("mtn_bj", "MTN MoMo", provider="MTN"), _m("moov_bj", "Moov Money", provider="Moov"), _m("celtiis_bj", "Celtiis Cash")],
    "CI": [_m("orange_ci", "Orange Money"), _m("mtn_ci", "MTN MoMo", provider="MTN"), _m("moov_ci", "Moov Money", provider="Moov"), _m("wave_ci", "Wave"), _m("djamo_ci", "Djamo")],
    "SN": [_m("wave_sn", "Wave"), _m("orange_sn", "Orange Money"), _m("free_sn", "Free Money"), _m("expresso_sn", "Expresso E-Money")],
    "TG": [_m("tmoney_tg", "T-Money"), _m("moov_tg", "Moov Money", provider="Moov")],
    "BF": [_m("orange_bf", "Orange Money"), _m("moov_bf", "Moov Money", provider="Moov"), _m("coris_bf", "Coris Money")],
    "ML": [_m("orange_ml", "Orange Money"), _m("moov_ml", "Moov Money", provider="Moov")],
    "NE": [_m("airtel_ne", "Airtel Money"), _m("moov_ne", "Moov Money", provider="Moov")],
    "CM": [_m("mtn_cm", "MTN MoMo"), _m("orange_cm", "Orange Money"), _m("yoomee_cm", "Yoomee Money")],
    "GH": [_m("mtn_gh", "MTN MoMo"), _m("vodafone_gh", "Vodafone Cash"), _m("airteltigo_gh", "AirtelTigo Money")],
    "NG": [_m("opay_ng", "OPay"), _m("bank_ng", "Virement bancaire", "bank")],
    "FR": [_m("sepa", "Virement SEPA", "bank")],
    "GN": [_m("orange_gn", "Orange Money"), _m("mtn_gn", "MTN MoMo")],
    "CD": [_m("mpesa_cd", "M-Pesa"), _m("orange_cd", "Orange Money"), _m("airtel_cd", "Airtel Money")],
    "KE": [_m("mpesa_ke", "M-Pesa"), _m("airtel_ke", "Airtel Money")],
    "UG": [_m("mtn_ug", "MTN MoMo"), _m("airtel_ug", "Airtel Money")],
    "RW": [_m("mtn_rw", "MTN MoMo"), _m("airtel_rw", "Airtel Money")],
    "TZ": [_m("mpesa_tz", "M-Pesa"), _m("tigo_tz", "Mixx by Yas"), _m("airtel_tz", "Airtel Money")],
}
# Moyens ajoutés à TOUS les pays : en plus des opérateurs locaux, carte, PayPal et virement sont toujours proposés.
UNIVERSAL = [CARD, PAYPAL, BANK]
DEFAULT = []


def methods_for_country(code):
    """Moyens de paiement proposés à un acheteur selon son pays."""
    pool = list(BY_COUNTRY.get(code, DEFAULT))
    keys = {m["key"] for m in pool}
    kinds = {m["kind"] for m in pool}
    for m in UNIVERSAL:
        if m["key"] in keys or (m["kind"] == "bank" and "bank" in kinds):   # pas de 2e virement si le pays a le sien
            continue
        pool.append(m)
    return pool


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
    from django.conf import settings

    if not getattr(settings, "ALLOW_SIMULATED_PAYMENTS", False):
        # Production : sans passerelle réelle branchée ici, on REFUSE (sinon n'importe qui obtiendrait des billets gratuits).
        return False, "", "Ce moyen de paiement n'est pas encore disponible. Utilisez MTN MoMo ou Moov Money."
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if method["kind"] == "momo" and digits.endswith("0000"):
        return False, "", "Paiement refusé par l'opérateur (solde insuffisant — simulation)."
    return True, f"SIM-{uuid.uuid4().hex[:10].upper()}", "Paiement validé."
