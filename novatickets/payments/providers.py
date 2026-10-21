"""Couche d'abstraction des passerelles de paiement.

Pour brancher une vraie passerelle (CinetPay, FedaPay, KKiaPay, Stripe…) :
  1. Créez une sous-classe de `PaymentProvider` implémentant `charge` et `payout`.
  2. Enregistrez-la dans `PROVIDERS`.
  3. Définissez la variable d'environnement PAYMENT_PROVIDER=<son code>.
Si la passerelle confirme le paiement plus tard (webhook), `charge` renvoie
`ChargeResult(status="pending")` et le webhook appelle ensuite
`payments.services.complete_payment(payment)`.
"""
from dataclasses import dataclass
from uuid import uuid4

from django.conf import settings


@dataclass
class ChargeResult:
    status: str  # "succeeded" | "failed" | "pending"
    provider_reference: str = ""
    message: str = ""
    redirect_url: str = ""  # pour les pages de paiement hébergées (carte)


@dataclass
class PayoutResult:
    status: str  # "completed" | "failed"
    provider_reference: str = ""
    message: str = ""


class PaymentProvider:
    code = "base"

    def charge(self, payment, method: str, phone: str) -> ChargeResult:
        raise NotImplementedError

    def payout(self, withdrawal) -> PayoutResult:
        raise NotImplementedError


class SimulationProvider(PaymentProvider):
    """Mode test : aucune transaction réelle.

    Règle de test : un numéro se terminant par « 00 » simule un paiement refusé
    (solde insuffisant) ; tous les autres numéros sont acceptés immédiatement.
    """

    code = "simulation"

    def charge(self, payment, method, phone):
        ref = f"SIM-{uuid4().hex[:12].upper()}"
        if method != "card" and phone.endswith("00"):
            return ChargeResult("failed", ref, "Paiement refusé (simulation : numéro se terminant par 00).")
        return ChargeResult("succeeded", ref, "Paiement simulé accepté.")

    def payout(self, withdrawal):
        ref = f"SIM-OUT-{uuid4().hex[:10].upper()}"
        if withdrawal.phone.endswith("00"):
            return PayoutResult("failed", ref, "Retrait refusé (simulation : numéro se terminant par 00).")
        return PayoutResult("completed", ref, "Retrait simulé effectué.")


PROVIDERS = {SimulationProvider.code: SimulationProvider}


def get_provider() -> PaymentProvider:
    try:
        return PROVIDERS[settings.PAYMENT_PROVIDER]()
    except KeyError:
        raise RuntimeError(f"Passerelle de paiement inconnue : {settings.PAYMENT_PROVIDER!r}")
