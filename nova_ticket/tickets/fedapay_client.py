"""
Client FedaPay minimal (sans dépendre du SDK officiel — juste `requests`).

Référence API utilisée :
- POST /v1/transactions            -> créer une transaction
- POST /v1/transactions/{id}/token -> obtenir l'URL de paiement hébergée (checkout_url)
- GET  /v1/transactions/{id}       -> relire le statut d'une transaction (vérification côté serveur)
Documentation : https://docs.fedapay.com/api-reference/transactions

Webhooks : FedaPay signe chaque appel via l'en-tête X-FEDAPAY-SIGNATURE, qui contient un
timestamp et une signature HMAC-SHA256 (même mécanique que Stripe, dont FedaPay reprend
explicitement le nom des méthodes — `Webhook.constructEvent`). Le format exact n'étant pas
publié en clair par FedaPay, `verify_webhook_signature` gère le format `t=...,s=...` documenté
(anti-rejeu) ET, en repli, une signature HMAC-SHA256 hexadécimale brute du corps de la requête.
⚠️ À valider une fois en possession de vraies clés, via le bouton "Envoyer un test" du dashboard
FedaPay (Développeurs > Webhooks) : si aucun des deux formats ne correspond, ajuste
`verify_webhook_signature` selon l'en-tête réellement reçu.
"""
import hashlib
import hmac
import json
import time

import requests
from django.conf import settings


class FedaPayError(Exception):
    """Erreur renvoyée par l'API FedaPay (requête invalide, clé absente, etc.)."""


class WebhookSignatureError(Exception):
    """La signature du webhook est absente, malformée, expirée ou invalide."""


def _headers():
    if not settings.FEDAPAY_SECRET_KEY:
        raise FedaPayError(
            "FEDAPAY_SECRET_KEY n'est pas configurée (variable d'environnement manquante)."
        )
    return {
        "Authorization": f"Bearer {settings.FEDAPAY_SECRET_KEY}",
        "Content-Type": "application/json",
    }


def creer_transaction(*, description, montant, devise, spectateur, callback_url):
    """Crée une transaction FedaPay pour l'achat d'un billet et renvoie la réponse JSON de l'API.

    `montant` doit être un entier (FedaPay n'accepte pas les décimales).
    `spectateur` est l'utilisateur (accounts.models.User) qui achète le billet.
    """
    payload = {
        "description": description,
        "amount": int(montant),
        "currency": {"iso": devise},
        "callback_url": callback_url,
        "customer": {
            "firstname": spectateur.prenoms or spectateur.username,
            "lastname": spectateur.nom or spectateur.username,
            "email": spectateur.email,
        },
    }
    if spectateur.telephone:
        payload["customer"]["phone_number"] = {"number": spectateur.telephone, "country": "bj"}

    try:
        r = requests.post(f"{settings.FEDAPAY_API_BASE}/transactions",
                           headers=_headers(), json=payload, timeout=15)
    except requests.RequestException as exc:
        raise FedaPayError(f"Impossible de joindre FedaPay (réseau) : {exc}") from exc
    if r.status_code >= 400:
        raise FedaPayError(f"Création de transaction refusée ({r.status_code}) : {r.text}")
    return r.json().get("v1/transaction", r.json())  # l'API renvoie parfois la ressource sous cette clé


def generer_token_paiement(transaction_id):
    """Demande l'URL de paiement hébergée (checkout_url) pour une transaction déjà créée."""
    try:
        r = requests.post(f"{settings.FEDAPAY_API_BASE}/transactions/{transaction_id}/token",
                           headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise FedaPayError(f"Impossible de joindre FedaPay (réseau) : {exc}") from exc
    if r.status_code >= 400:
        raise FedaPayError(f"Génération du lien de paiement refusée ({r.status_code}) : {r.text}")
    data = r.json()
    checkout_url = data.get("url") or data.get("token", {}).get("url") if isinstance(data.get("token"), dict) else data.get("url")
    if not checkout_url:
        raise FedaPayError(f"Réponse FedaPay inattendue (pas d'URL de paiement) : {data}")
    return checkout_url


def recuperer_transaction(transaction_id):
    """Relit l'état actuel d'une transaction directement depuis l'API (vérification côté serveur,
    en complément — jamais en remplacement — de la vérification de signature du webhook)."""
    try:
        r = requests.get(f"{settings.FEDAPAY_API_BASE}/transactions/{transaction_id}",
                          headers=_headers(), timeout=15)
    except requests.RequestException as exc:
        raise FedaPayError(f"Impossible de joindre FedaPay (réseau) : {exc}") from exc
    if r.status_code >= 400:
        raise FedaPayError(f"Lecture de la transaction impossible ({r.status_code}) : {r.text}")
    data = r.json()
    return data.get("v1/transaction", data)


def initier_paiement(*, description, montant, devise, spectateur, callback_url):
    """Raccourci : crée la transaction puis renvoie directement (transaction_id, checkout_url)."""
    transaction = creer_transaction(description=description, montant=montant, devise=devise,
                                     spectateur=spectateur, callback_url=callback_url)
    transaction_id = transaction["id"]
    checkout_url = generer_token_paiement(transaction_id)
    return transaction_id, checkout_url


# --- Vérification de signature des webhooks ---

REPLAY_TOLERANCE_SECONDS = 5 * 60  # rejette les webhooks dont le timestamp a plus de 5 minutes


def _hmac_hex(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def verify_webhook_signature(raw_body: bytes, signature_header: str, secret: str) -> dict:
    """Vérifie la signature d'un webhook FedaPay et renvoie l'événement (dict) si elle est valide.

    Lève `WebhookSignatureError` si la signature est absente, mal formée, expirée ou invalide.
    """
    if not secret:
        raise WebhookSignatureError("FEDAPAY_WEBHOOK_SECRET n'est pas configuré.")
    if not signature_header:
        raise WebhookSignatureError("En-tête X-FEDAPAY-SIGNATURE manquant.")

    body_str = raw_body.decode("utf-8")
    valid = False

    # Format principal (documenté par FedaPay comme protégé contre le rejeu par un timestamp) :
    # "t=<timestamp_unix>,s=<hmac_sha256_hex>", signature calculée sur "<timestamp>.<corps>".
    parts = dict(p.split("=", 1) for p in signature_header.split(",") if "=" in p)
    if "t" in parts and "s" in parts:
        timestamp, provided_sig = parts["t"], parts["s"]
        if abs(time.time() - int(timestamp)) > REPLAY_TOLERANCE_SECONDS:
            raise WebhookSignatureError("Timestamp du webhook trop ancien (possible rejeu).")
        expected_sig = _hmac_hex(secret, f"{timestamp}.{body_str}")
        valid = hmac.compare_digest(expected_sig, provided_sig)
    else:
        # Repli : certaines intégrations observées en pratique envoient directement le HMAC-SHA256
        # hexadécimal du corps brut, sans préfixe "t=/s=". On l'accepte aussi par sécurité.
        expected_sig = _hmac_hex(secret, body_str)
        valid = hmac.compare_digest(expected_sig, signature_header.strip())

    if not valid:
        raise WebhookSignatureError("Signature invalide.")

    return json.loads(body_str)
