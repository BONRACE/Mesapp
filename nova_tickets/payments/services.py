"""Logique métier du paiement Mobile Money, isolée des vues.

- normalisation du numéro, génération de la référence
- client de passerelle (simulation ou appel réel structuré)
- vérification de la signature du webhook
- application du statut (idempotente et protégée contre les doubles notifications)
"""
import hashlib
import hmac
import json
import logging
import re
import secrets
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation

import phonenumbers
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Transaction

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------- réglages

def _setting(name, default):
    return getattr(settings, name, default)


# Statuts renvoyés par la passerelle, ramenés à nos deux états finaux.
APPROVED_STATUSES = {"APPROVED", "SUCCESS", "SUCCESSFUL", "COMPLETED"}
REFUSED_STATUSES = {"FAILED", "FAILURE", "DECLINED", "REJECTED", "REFUSED", "CANCELLED", "CANCELED", "EXPIRED"}

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sans 0/O/1/I pour éviter les confusions


class PaymentError(Exception):
    """Erreur affichable à l'utilisateur."""


# ----------------------------------------------------------------------------- numéro & référence

def normalize_phone(raw, country="BJ"):
    """Renvoie le numéro au format international sans « + » (ex. 2290197000001).

    Bénin : règle stricte (10 chiffres 01XXXXXXXX depuis la réforme ; « 0197 00 00 01 », « +229 01 97 00 00 01 »
    et l'ancien format à 8 chiffres sont acceptés). Autres pays : analyse par la bibliothèque phonenumbers
    (« 07 07 00 00 04 » en Côte d'Ivoire, « 90 00 00 06 » au Togo…). Lève PaymentError si le numéro est invalide.
    """
    if country != "BJ":
        try:
            number = phonenumbers.parse(raw or "", country)
        except phonenumbers.NumberParseException:
            raise PaymentError("Numéro Mobile Money invalide pour votre pays.")
        if not phonenumbers.is_possible_number(number):
            raise PaymentError("Numéro Mobile Money invalide pour votre pays.")
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164).lstrip("+")
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00229"):
        digits = digits[5:]
    elif digits.startswith("229"):
        digits = digits[3:]
    if len(digits) == 8:          # ancien format
        digits = "01" + digits
    if not (len(digits) == 10 and digits.startswith("01")):
        raise PaymentError("Numéro Mobile Money invalide. Exemple : 01 97 00 00 01.")
    return "229" + digits


def parse_amount(raw):
    try:
        amount = Decimal(str(raw)).quantize(Decimal("1"))  # le FCFA n'a pas de centimes
    except (InvalidOperation, ValueError):
        raise PaymentError("Montant invalide.")
    if amount < Decimal(_setting("MOMO_MIN_AMOUNT", 100)):
        raise PaymentError(f"Le montant minimum est de {_setting('MOMO_MIN_AMOUNT', 100)} FCFA.")
    if amount > Decimal(_setting("MOMO_MAX_AMOUNT", 2_000_000)):
        raise PaymentError("Montant supérieur au plafond autorisé.")
    return amount


def generate_reference():
    """Référence marchand lisible et unique, ex. NT-20261026-K7F3Q9XD."""
    return f"NT-{timezone.localdate():%Y%m%d}-" + "".join(secrets.choice(ALPHABET) for _ in range(8))


# ----------------------------------------------------------------------------- création

def create_transaction(*, user_email, phone_number, amount, provider, order=None, business_card=None, country="BJ"):
    """Crée une transaction PENDING avec une référence unique.

    Tunnel de commande : passer `order=` ; le montant est alors FORCÉ au total de la commande
    (jamais une valeur venue du navigateur). Même principe pour `business_card=`.
    """
    if order is not None:
        amount = order.total
    phone = normalize_phone(phone_number, country)
    amount = parse_amount(amount)
    if provider not in Transaction.Provider.values:
        raise PaymentError("Opérateur non pris en charge.")
    for _ in range(5):  # la collision est quasi impossible, mais la contrainte unique tranche
        try:
            with transaction.atomic():
                return Transaction.objects.create(
                    user_email=user_email.strip().lower(), phone_number=phone, amount=amount,
                    provider=provider, reference=generate_reference(), order=order, business_card=business_card,
                )
        except IntegrityError:
            continue
    raise PaymentError("Impossible de générer une référence unique, réessayez.")


# ----------------------------------------------------------------------------- passerelle

def push_payment(tx, callback_url):
    """Demande à la passerelle d'envoyer la demande de validation (USSD push) sur le téléphone du client.

    Mode « simulation » (défaut) : aucun appel réseau, la passerelle répond immédiatement.
    Mode « live » : appel HTTP JSON vers MOMO_API_BASE_URL — adapter les champs au contrat
    de votre agrégateur (FedaPay, KkiaPay, CinetPay, API MTN MoMo / Moov directe…).

    Renvoie la référence côté passerelle. Lève PaymentError si la passerelle refuse l'appel.
    """
    if _setting("MOMO_GATEWAY_MODE", "simulation") == "simulation":
        return f"SIM-{secrets.token_hex(5).upper()}"

    payload = {
        "reference": tx.reference,
        "amount": int(tx.amount),
        "currency": _setting("MOMO_CURRENCY", "XOF"),
        "provider": tx.provider,            # "MTN" | "Moov" — certains agrégateurs attendent "mtn_open" / "moov"…
        "phone_number": tx.phone_number,
        "customer_email": tx.user_email,
        "callback_url": callback_url,       # URL du webhook ci-dessous
        "description": f"Billets NovaTickets {tx.reference}",
    }
    req = urllib.request.Request(
        _setting("MOMO_API_BASE_URL", "").rstrip("/") + "/collect",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_setting('MOMO_API_KEY', '')}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode() or "{}")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logger.exception("Échec de l'appel push pour %s", tx.reference)
        raise PaymentError("Le service Mobile Money est momentanément indisponible.") from exc
    return str(data.get("transaction_id") or data.get("id") or "")


# ----------------------------------------------------------------------------- webhook

def sign(body: bytes) -> str:
    """Signature HMAC-SHA256 (hex) d'un corps de requête avec le secret partagé."""
    secret = _setting("MOMO_WEBHOOK_SECRET", "").encode()
    return hmac.new(secret, body, hashlib.sha256).hexdigest()


def signature_is_valid(body: bytes, header_value: str) -> bool:
    """Compare en temps constant la signature reçue à celle que nous calculons."""
    if not _setting("MOMO_WEBHOOK_SECRET", "") or not header_value:
        return False
    return hmac.compare_digest(sign(body), header_value.strip().lower())


def map_status(raw):
    """'APPROVED'/'SUCCESS'… -> SUCCESS ; 'DECLINED'/'CANCELLED'… -> FAILED ; sinon None (inconnu)."""
    value = (raw or "").strip().upper()
    if value in APPROVED_STATUSES:
        return Transaction.Status.SUCCESS
    if value in REFUSED_STATUSES:
        return Transaction.Status.FAILED
    return None


def apply_gateway_status(reference, raw_status, gateway_reference="", amount=None, reason=""):
    """Met à jour la transaction à partir d'une notification de la passerelle.

    Garanties :
    - verrou de ligne : deux webhooks simultanés ne se marchent pas dessus ;
    - idempotence : une transaction déjà SUCCESS/FAILED n'est jamais modifiée (rejeu, doublon,
      notification contradictoire tardive) ;
    - contrôle du montant : un montant différent de celui attendu n'est jamais validé.

    Renvoie (transaction, changed). Lève Transaction.DoesNotExist si la référence est inconnue,
    PaymentError si le statut est inconnu ou le montant incohérent.
    """
    new_status = map_status(raw_status)
    if new_status is None:
        raise PaymentError(f"Statut inconnu : {raw_status!r}")

    with transaction.atomic():
        tx = Transaction.objects.select_for_update().get(reference=reference)
        if not tx.is_pending:
            return tx, False

        if new_status == Transaction.Status.SUCCESS and amount is not None:
            try:
                paid = Decimal(str(amount))
            except InvalidOperation:
                raise PaymentError("Montant illisible dans la notification.")
            if paid != tx.amount:
                logger.error("Montant incohérent pour %s : attendu %s, reçu %s", reference, tx.amount, paid)
                raise PaymentError("Montant incohérent.")

        tx.status = new_status
        if gateway_reference:
            tx.gateway_reference = gateway_reference[:80]
        if new_status == Transaction.Status.SUCCESS:
            tx.paid_at = timezone.now()
        else:
            tx.failure_reason = (reason or f"Refusé par l'opérateur ({raw_status})")[:200]
        tx.save()
        if new_status == Transaction.Status.SUCCESS:
            # Dans le même bloc atomique : si la livraison échoue, le statut est annulé aussi,
            # le webhook répond 500 et la passerelle renverra la notification (pas de paiement « perdu »).
            fulfil(tx)

    if new_status == Transaction.Status.SUCCESS:
        on_payment_success(tx)
    return tx, True


def fulfil(tx):
    """Livre ce qui a été payé. Idempotent (finalize_order / activate_card ne font rien au 2e appel)."""
    if tx.order_id:
        from orders.services import finalize_order, schedule_receipt
        order, newly_paid = finalize_order(
            tx.order, method_key=f"momo_{tx.provider.lower()}", method_label=tx.get_provider_display(),
            phone=tx.phone_number, provider_ref=tx.gateway_reference or tx.reference,
        )
        if newly_paid:
            schedule_receipt(order)       # reçu e-mail envoyé après validation de la transaction SQL
        elif order.status == "paid" and order.payment_ref not in (tx.gateway_reference, tx.reference):
            # Deux paiements aboutis pour la même commande : à rembourser manuellement.
            logger.error("DOUBLE PAIEMENT sur la commande %s (transaction %s)", order.reference, tx.reference)
    elif tx.business_card_id:
        from cards.services import activate_card
        activate_card(tx.business_card)
        transaction.on_commit(lambda: send_transaction_receipt(tx))
    else:
        transaction.on_commit(lambda: send_transaction_receipt(tx))


def launch_push(tx, callback_url):
    """Envoie le push USSD ; si la passerelle refuse l'appel, la transaction passe directement en FAILED."""
    try:
        tx.gateway_reference = push_payment(tx, callback_url)
        tx.save(update_fields=["gateway_reference"])
    except PaymentError as exc:
        apply_gateway_status(tx.reference, "FAILED", reason=str(exc))


def on_payment_success(tx):
    """Point d'extension : appelé une fois que la transaction est passée à SUCCESS (notifications, stats…)."""
    logger.info("Paiement confirmé : %s (%s FCFA)", tx.reference, tx.amount)


def transaction_receipt_data(tx):
    """Données du reçu d'une transaction hors commande (activation de carte, paiement autonome)."""
    label = "Activation de la carte de visite" if tx.business_card_id else "Paiement Mobile Money"
    return {
        "reference": tx.reference, "date": tx.paid_at or tx.created_at, "thanks": "Merci pour votre paiement !",
        "event": None,
        "spectator": [("Email", tx.user_email), ("Téléphone", tx.masked_phone)],
        "details_title": "Détails du paiement",
        "details": [("Objet", label), ("Référence", tx.reference), ("Moyen de paiement", tx.get_provider_display()),
                    ("Réf. opérateur", tx.gateway_reference or "—")],
        "status": "Payé", "total": int(tx.amount), "signature": None, "organizer": None, "qr": None,
    }


def transaction_receipt_pdf(tx):
    """Reçu PDF d'une transaction réussie (commande -> reçu de commande ; sinon reçu générique)."""
    if tx.order_id:
        from orders.services import order_receipt_pdf
        return order_receipt_pdf(tx.order)
    from core.pdf import render_receipt
    return render_receipt(transaction_receipt_data(tx))


def send_transaction_receipt(tx):
    """Reçu e-mail automatique d'un paiement qui ne passe pas par une commande (carte de visite, paiement autonome)."""
    from orders.services import build_receipt_email

    try:
        msg = build_receipt_email(transaction_receipt_data(tx), to=tx.user_email, subject=f"Votre reçu {settings.PLATFORM_NAME} — {tx.reference}",
                                  attachments=[(f"recu-{tx.reference}.pdf", transaction_receipt_pdf(tx))])
        msg.send(fail_silently=True)
    except Exception:  # un reçu raté ne doit jamais annuler un paiement validé
        logger.exception("Envoi du reçu impossible pour %s", tx.reference)

