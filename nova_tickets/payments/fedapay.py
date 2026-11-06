"""Intégration FedaPay (https://fedapay.com) : page de paiement hébergée (Mobile Money MTN / Moov / Celtiis, cartes…).

Parcours
1. On crée une transaction côté FedaPay (POST /v1/transactions) puis son lien de paiement (POST /v1/transactions/{id}/token).
2. Le client est redirigé vers ce lien, paie avec le moyen de son choix, puis revient sur notre page de suivi (callback_url).
3. FedaPay prévient aussi notre webhook (/paiement/webhook/). Dans les DEUX cas, le statut n'est JAMAIS cru sur parole :
   on le relit auprès de l'API FedaPay (GET /v1/transactions/{id}) avec la clé secrète — c'est ce que recommande FedaPay —
   puis on applique le résultat (montant contrôlé, traitement idempotent) avec `apply_gateway_status`.
   Une notification falsifiée ne peut donc rien valider.

Réglages (.env) : PAYMENT_GATEWAY=fedapay, FEDAPAY_ENV=sandbox|live, FEDAPAY_SECRET_KEY, FEDAPAY_WEBHOOK_SECRET.
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request

from django.conf import settings
from django.urls import reverse

from .models import Transaction
from .services import PaymentError, apply_gateway_status, create_transaction

logger = logging.getLogger(__name__)

API_URLS = {"sandbox": "https://sandbox-api.fedapay.com/v1", "live": "https://api.fedapay.com/v1"}

# Statuts FedaPay -> vocabulaire de apply_gateway_status. « pending » : on attend (aucun changement).
REMOTE_APPROVED = {"approved", "transferred"}
REMOTE_REFUSED = {"declined", "canceled", "cancelled"}


def _setting(name, default=""):
    return getattr(settings, name, default)


def enabled():
    """FedaPay est actif si PAYMENT_GATEWAY=fedapay ET la clé secrète est renseignée."""
    return _setting("PAYMENT_GATEWAY", "simulation") == "fedapay" and bool(_setting("FEDAPAY_SECRET_KEY"))


def base_url():
    return API_URLS["live" if _setting("FEDAPAY_ENV", "sandbox") == "live" else "sandbox"]


# ----------------------------------------------------------------------------- appels HTTP

def _request(method, path, payload=None):
    """Appel JSON authentifié vers l'API FedaPay. Renvoie le JSON décodé ; lève PaymentError sans jamais exposer la clé."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base_url() + path, data=data, method=method, headers={
        "Authorization": f"Bearer {_setting('FEDAPAY_SECRET_KEY')}", "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=int(_setting("FEDAPAY_TIMEOUT", 15))) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode()[:300]
        except Exception:
            pass
        logger.error("FedaPay %s %s -> HTTP %s %s", method, path, exc.code, detail)
        raise PaymentError("Le service de paiement a refusé la demande. Réessayez ou contactez le support.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.error("FedaPay %s %s injoignable : %s", method, path, exc)
        raise PaymentError("Le service de paiement est momentanément indisponible. Réessayez dans un instant.") from exc


def _entity(data):
    """L'API enveloppe l'objet sous une clé du type « v1/transaction » ; on accepte aussi un objet à plat."""
    if isinstance(data, dict):
        for key in ("v1/transaction", "transaction"):
            if isinstance(data.get(key), dict):
                return data[key]
        if "id" in data:
            return data
    return {}


# ----------------------------------------------------------------------------- création

def _customer(user):
    first = (user.first_name or "Client")[:60]
    last = (user.last_name or user.username or "NovaTickets")[:60]
    customer = {"firstname": first, "lastname": last, "email": user.email}
    phone = (user.phone or "").strip()
    if phone.startswith("+") and 8 <= len(phone) <= 16:
        customer["phone_number"] = {"number": phone, "country": (user.country or "bj").lower()}
    return customer


def start_checkout(request, *, user, amount, description, order=None, business_card=None, subscription=None):
    """Crée la transaction locale + la transaction FedaPay + le lien de paiement. Renvoie la Transaction (checkout_url renseignée).

    `amount` vient toujours du serveur (total de la commande, prix de la carte, prix de l'abonnement), jamais du navigateur.
    """
    if not enabled():
        raise PaymentError("Le paiement en ligne n'est pas configuré.")
    tx = create_transaction(user_email=user.email, phone_number=user.phone or "", amount=amount,
                            provider=Transaction.Provider.FEDAPAY, order=order, business_card=business_card,
                            subscription=subscription, country=user.country)
    return_url = request.build_absolute_uri(reverse("payments:status", args=[tx.pk]))
    try:
        created = _entity(_request("POST", "/transactions", {
            "description": f"{settings.PLATFORM_NAME} — {description} ({tx.reference})"[:250],
            "amount": int(tx.amount), "currency": {"iso": _setting("FEDAPAY_CURRENCY", "XOF")},
            "callback_url": return_url, "customer": _customer(user),
        }))
        fid = created.get("id")
        if not fid:
            raise PaymentError("Réponse inattendue du service de paiement.")
        token = _request("POST", f"/transactions/{fid}/token")
        url = token.get("url") or ""
        if not url.startswith("https://"):
            raise PaymentError("Lien de paiement indisponible.")
    except PaymentError as exc:
        apply_gateway_status(tx.reference, "FAILED", reason=str(exc))
        raise
    tx.gateway_reference, tx.checkout_url = str(fid), url[:400]
    tx.save(update_fields=["gateway_reference", "checkout_url"])
    return tx


def next_url(tx):
    """Où envoyer le client : la page FedaPay tant que la transaction est en attente, sinon notre page de suivi."""
    if tx.is_pending and tx.checkout_url:
        return tx.checkout_url
    return reverse("payments:status", args=[tx.pk])


# ----------------------------------------------------------------------------- synchronisation (source de vérité = l'API)

def sync(tx):
    """Relit la transaction chez FedaPay et applique le résultat. Renvoie la transaction à jour. N'échoue jamais bruyamment."""
    if tx.provider != Transaction.Provider.FEDAPAY or not tx.is_pending or not tx.gateway_reference or not enabled():
        return tx
    try:
        remote = _entity(_request("GET", f"/transactions/{tx.gateway_reference}"))
    except PaymentError:
        return tx
    status = str(remote.get("status", "")).lower()
    try:
        if status in REMOTE_APPROVED:
            tx, _ = apply_gateway_status(tx.reference, "APPROVED", gateway_reference=str(remote.get("id", tx.gateway_reference)),
                                         amount=remote.get("amount"))
        elif status in REMOTE_REFUSED:
            tx, _ = apply_gateway_status(tx.reference, "DECLINED", reason=f"Paiement {status} sur FedaPay")
    except PaymentError as exc:               # montant incohérent : jamais validé, on journalise
        logger.error("FedaPay : transaction %s non validée (%s)", tx.reference, exc)
    tx.refresh_from_db()
    return tx


# ----------------------------------------------------------------------------- webhook

def signature_is_valid(body, header):
    """Vérifie l'en-tête X-FEDAPAY-SIGNATURE avec le secret du point de terminaison (FEDAPAY_WEBHOOK_SECRET).

    Format pris en charge : « t=<horodatage>,s=<HMAC-SHA256 hex de "<horodatage>.<corps>"> » (format des SDK FedaPay),
    avec rejet des horodatages trop anciens ; ou, à défaut, HMAC-SHA256 hex du corps brut (éventuellement préfixé « sha256= »).
    Comme le statut est de toute façon relu auprès de l'API (sync), cette vérification est une première barrière, pas la seule.
    """
    secret = _setting("FEDAPAY_WEBHOOK_SECRET", "").encode()
    header = (header or "").strip()
    if not secret or not header:
        return False
    parts = {}
    for chunk in header.split(","):
        if "=" in chunk:
            k, v = chunk.split("=", 1)
            parts[k.strip()] = v.strip()
    if "t" in parts and "s" in parts:
        try:
            ts = float(parts["t"])
        except ValueError:
            return False
        if ts > 1e11:                                        # millisecondes
            ts /= 1000
        if abs(time.time() - ts) > int(_setting("FEDAPAY_WEBHOOK_TOLERANCE", 600)):
            return False
        expected = hmac.new(secret, parts["t"].encode() + b"." + body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, parts["s"].lower())
    expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.lower().removeprefix("sha256="))


def handle_webhook(body, header):
    """Traite une notification FedaPay. Renvoie (code HTTP, dict JSON)."""
    if not signature_is_valid(body, header):
        logger.warning("Webhook FedaPay refusé : signature invalide")
        return 403, {"detail": "Signature invalide."}
    try:
        payload = json.loads(body.decode())
        entity = payload.get("entity") or payload.get("data") or {}
        if isinstance(entity, dict) and isinstance(entity.get("object"), dict):
            entity = entity["object"]
        fid = str(entity.get("id", ""))
    except (ValueError, AttributeError):
        return 400, {"detail": "Corps invalide."}
    if not fid:
        return 400, {"detail": "Identifiant de transaction manquant."}
    tx = Transaction.objects.filter(provider=Transaction.Provider.FEDAPAY, gateway_reference=fid).first()
    if tx is None:
        return 200, {"ignored": True}              # transaction inconnue de nous : on répond 200 pour stopper les relances
    tx = sync(tx)                                    # le statut vient de l'API, pas du contenu du webhook
    return 200, {"reference": tx.reference, "status": tx.status}
