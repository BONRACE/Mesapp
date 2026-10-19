"""Passerelles de paiement.

Contrat d'un fournisseur :
  create(payment, order, user)  -> {"provider_ref": str, "checkout_url": str}
  fetch_status(payment)         -> "pending" | "succeeded" | "failed"   (vérité côté serveur du fournisseur)

Principe de sécurité : on ne croit jamais le contenu d'un webhook ni l'URL de retour du navigateur.
Ils servent seulement de déclencheur ; le statut est relu auprès du fournisseur via fetch_status().

Passerelles disponibles : mock (démo), fedapay, cinetpay. Ajouter Stripe = une classe de plus + une entrée dans PROVIDERS.
"""
import logging

import requests
from django.conf import settings

log = logging.getLogger(__name__)


class ProviderError(Exception):
    pass


class MockProvider:
    """Passerelle de démonstration : une page « paiement » est simulée par le frontend."""

    name = "mock"

    def create(self, payment, order, user):
        return {
            "provider_ref": f"mock_{payment.id.hex[:12]}",
            "checkout_url": f"{settings.FRONTEND_URL}/app.html#/pay/{payment.id}",
        }

    def fetch_status(self, payment):
        return payment.status  # le statut ne change que via /payments/mock/<id>/confirm/


class FedaPayProvider:
    """FedaPay (Bénin) — Mobile Money MTN/Moov + cartes. https://docs.fedapay.com

    Flux : POST /transactions -> POST /transactions/{id}/token -> redirection vers `url`.
    Les réponses sont « déballées » de façon tolérante (la clé d'enveloppe varie selon la version de l'API).
    À valider sur le bac à sable FedaPay avant la mise en production.
    """

    name = "fedapay"
    OK = {"approved", "transferred"}
    KO = {"declined", "canceled", "cancelled", "refunded"}

    @property
    def base(self):
        host = "https://api.fedapay.com" if settings.FEDAPAY_ENV == "live" else "https://sandbox-api.fedapay.com"
        return f"{host}/v1"

    def _call(self, method, path, **kw):
        if not settings.FEDAPAY_SECRET_KEY:
            raise ProviderError("FEDAPAY_SECRET_KEY non configurée.")
        try:
            r = requests.request(
                method, f"{self.base}{path}", timeout=12,
                headers={"Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}", "Content-Type": "application/json"}, **kw,
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            log.warning("FedaPay %s %s: %s", method, path, e)
            raise ProviderError("La passerelle de paiement est indisponible, réessayez.") from e

    @staticmethod
    def _unwrap(data):
        if isinstance(data, dict) and "id" in data:
            return data
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return v[0]
                if isinstance(v, dict) and "id" in v:
                    return v
        raise ProviderError("Réponse inattendue de la passerelle.")

    def create(self, payment, order, user):
        first, _, last = (user.full_name or "Client").partition(" ")
        body = {
            "description": f"EcoKolekt — commande {str(order.id)[:8]}",
            "amount": payment.amount,
            "currency": {"iso": payment.currency},
            "callback_url": f"{settings.FRONTEND_URL}/app.html#/orders",
            "customer": {
                "firstname": first, "lastname": last or first,
                "phone_number": {"number": user.phone.lstrip("+")[3:] if user.phone.startswith("+229") else user.phone, "country": "bj"},
            },
        }
        tx = self._unwrap(self._call("POST", "/transactions", json=body))
        tok = self._call("POST", f"/transactions/{tx['id']}/token")
        url = tok.get("url") or (tok.get("token") and f"https://{'process' if settings.FEDAPAY_ENV == 'live' else 'sandbox-process'}.fedapay.com/{tok['token']}")
        if not url:
            raise ProviderError("Lien de paiement indisponible.")
        return {"provider_ref": str(tx["id"]), "checkout_url": url}

    def fetch_status(self, payment):
        tx = self._unwrap(self._call("GET", f"/transactions/{payment.provider_ref}"))
        s = str(tx.get("status", "")).lower()
        return "succeeded" if s in self.OK else "failed" if s in self.KO else "pending"


class CinetPayProvider:
    """CinetPay (Afrique de l'Ouest) — Mobile Money + cartes. https://docs.cinetpay.com  (API Checkout v2)

    Flux : POST /v2/payment -> redirection vers `payment_url` ; le statut est relu avec POST /v2/payment/check.
    Notre `transaction_id` (unique, dérivé de l'id du paiement) tient lieu de provider_ref.
    À valider sur le compte de test CinetPay avant la mise en production.
    """

    name = "cinetpay"
    BASE = "https://api-checkout.cinetpay.com/v2"

    def _post(self, path, payload):
        if not (settings.CINETPAY_API_KEY and settings.CINETPAY_SITE_ID):
            raise ProviderError("CINETPAY_API_KEY / CINETPAY_SITE_ID non configurés.")
        body = {"apikey": settings.CINETPAY_API_KEY, "site_id": settings.CINETPAY_SITE_ID, **payload}
        try:
            r = requests.post(f"{self.BASE}{path}", json=body, timeout=12)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("CinetPay %s: %s", path, e)
            raise ProviderError("La passerelle de paiement est indisponible, réessayez.") from e

    @staticmethod
    def amount_for(payment) -> int:
        """CinetPay exige un montant multiple de 5 en XOF : on arrondit au multiple supérieur."""
        return -(-payment.amount // 5) * 5

    def create(self, payment, order, user):
        txn = f"EK{payment.id.hex[:18]}"
        first, _, last = (user.full_name or "Client").partition(" ")
        data = self._post("/payment", {
            "transaction_id": txn, "amount": self.amount_for(payment), "currency": payment.currency,
            "description": f"EcoKolekt commande {str(order.id)[:8]}", "lang": "fr",
            "channels": "CREDIT_CARD" if payment.method == "card" else "MOBILE_MONEY",
            "notify_url": f"{settings.BACKEND_URL}/api/payments/webhook/cinetpay/",
            "return_url": f"{settings.FRONTEND_URL}/app.html#/orders",
            "customer_name": first, "customer_surname": last or first, "customer_phone_number": user.phone,
            "customer_country": "BJ",
        })
        url = (data.get("data") or {}).get("payment_url")
        if str(data.get("code")) != "201" or not url:
            raise ProviderError("Lien de paiement indisponible.")
        return {"provider_ref": txn, "checkout_url": url}

    def fetch_status(self, payment):
        data = self._post("/payment/check", {"transaction_id": payment.provider_ref})
        info = data.get("data") or {}
        status = str(info.get("status", "")).upper()
        if str(data.get("code")) == "00" and status == "ACCEPTED":
            if int(float(info.get("amount") or 0)) < self.amount_for(payment):
                log.error("CinetPay %s: montant payé inférieur au montant dû", payment.provider_ref)
                return "failed"
            return "succeeded"
        return "failed" if status == "REFUSED" or str(data.get("code")) in {"600", "627"} else "pending"


PROVIDERS = {"mock": MockProvider, "fedapay": FedaPayProvider, "cinetpay": CinetPayProvider}


def get_provider(name=None):
    name = name or settings.PAYMENT_DEFAULT_PROVIDER
    if name not in PROVIDERS:
        raise ProviderError(f"Passerelle inconnue : {name}")
    return PROVIDERS[name]()
