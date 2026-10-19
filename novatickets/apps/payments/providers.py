"""Couche d'abstraction des passerelles de paiement.

Chaque moyen de paiement est un « provider ». Pour brancher une vraie passerelle
(FedaPay, KkiaPay, Stripe…), on crée une classe qui implémente `initier` et
`verifier`, puis on l'ajoute à PROVIDERS. Le mode `simulation` permet de tester
tout le parcours sans argent réel.
"""
import secrets
from dataclasses import dataclass

from django.conf import settings

from apps.core.countries import get_pays


@dataclass
class ResultatPaiement:
    succes: bool
    reference_externe: str
    message: str = ""
    url_validation: str = ""


class ProviderBase:
    slug = "base"
    libelle = "Base"

    def initier(self, paiement, telephone=""):
        raise NotImplementedError

    def verifier(self, paiement):
        raise NotImplementedError


class ProviderSimulation(ProviderBase):
    """Simule une validation immédiate. Ne jamais utiliser en production."""

    slug = "simulation"
    libelle = "Simulation (test)"

    def initier(self, paiement, telephone=""):
        return ResultatPaiement(True, f"SIM-{secrets.token_hex(5).upper()}", "Paiement simulé validé.")

    def verifier(self, paiement):
        return ResultatPaiement(True, paiement.reference, "Simulation : toujours validé.")


class ProviderMobileMoney(ProviderBase):
    """Squelette pour les opérateurs mobile money (MTN MoMo, Moov, Celtiis…).

    Brancher ici l'API réelle de l'agrégateur (ex. FedaPay ou KkiaPay) :
    initier -> création de la transaction et envoi de la demande USSD/push ;
    verifier -> interrogation ou réception du webhook signé.
    """

    def __init__(self, slug, libelle, operateurs):
        self.slug = slug
        self.libelle = libelle
        self.operateurs = operateurs

    def initier(self, paiement, telephone=""):
        # TODO production : appel HTTP à l'API de l'agrégateur avec la clé secrète.
        return ResultatPaiement(
            True,
            f"{self.slug.upper()}-{secrets.token_hex(4).upper()}",
            f"Demande envoyée sur {telephone or 'votre téléphone'} (simulation).",
        )

    def verifier(self, paiement):
        return ResultatPaiement(True, paiement.reference, "Transaction confirmée (simulation).")


# Moyens de paiement par pays (code ISO). Ajouter un pays ici suffit pour l'afficher.
MOYENS_PAR_PAYS = {
    "BJ": ["mtn_momo", "moov_money", "celtiis_cash"],
    "TG": ["moov_money", "t_money"],
    "CI": ["orange_money", "mtn_momo", "moov_money", "wave"],
    "SN": ["orange_money", "wave", "free_money"],
    "BF": ["orange_money", "moov_money"],
    "NE": ["airtel_money", "moov_money"],
    "ML": ["orange_money", "moov_money"],
    "CM": ["mtn_momo", "orange_money"],
    "GH": ["mtn_momo", "telecel_cash"],
    "NG": ["opay", "paystack_card"],
}
MOYEN_CARTE = "carte_bancaire"

PROVIDERS = {
    "simulation": ProviderSimulation(),
    "mtn_momo": ProviderMobileMoney("mtn_momo", "MTN MoMo", ["MTN"]),
    "moov_money": ProviderMobileMoney("moov_money", "Moov Money", ["Moov"]),
    "celtiis_cash": ProviderMobileMoney("celtiis_cash", "Celtiis Cash", ["Celtiis"]),
    "orange_money": ProviderMobileMoney("orange_money", "Orange Money", ["Orange"]),
    "wave": ProviderMobileMoney("wave", "Wave", ["Wave"]),
    "free_money": ProviderMobileMoney("free_money", "Free Money", ["Free"]),
    "t_money": ProviderMobileMoney("t_money", "T-Money", ["T-Money"]),
    "airtel_money": ProviderMobileMoney("airtel_money", "Airtel Money", ["Airtel"]),
    "telecel_cash": ProviderMobileMoney("telecel_cash", "Telecel Cash", ["Telecel"]),
    "opay": ProviderMobileMoney("opay", "OPay", ["OPay"]),
    MOYEN_CARTE: ProviderMobileMoney(MOYEN_CARTE, "Carte bancaire", []),
    "paystack_card": ProviderMobileMoney("paystack_card", "Carte (Paystack)", []),
}


def moyens_pour_pays(code_pays):
    """Liste des moyens de paiement disponibles pour le pays de l'acheteur."""
    slugs = list(MOYENS_PAR_PAYS.get(code_pays, []))
    if getattr(settings, "NOVATICKETS", {}).get("PROVIDER_PAIEMENT") == "simulation":
        slugs = ["simulation"] + slugs
    if MOYEN_CARTE not in slugs:
        slugs.append(MOYEN_CARTE)  # carte bancaire en option, comme demandé
    return [PROVIDERS[s] for s in slugs if s in PROVIDERS]


def get_provider(slug):
    return PROVIDERS.get(slug)
