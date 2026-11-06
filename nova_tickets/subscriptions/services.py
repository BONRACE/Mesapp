"""Abonnement organisateur : prix, état, activation (idempotente) et paiement (tous les moyens du pays)."""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Subscription

logger = logging.getLogger(__name__)


def price():
    return int(getattr(settings, "SUBSCRIPTION_PRICE", 5000))


def duration_days():
    return int(getattr(settings, "SUBSCRIPTION_DAYS", 30))


def required():
    """Si True, un organisateur sans abonnement actif ne peut ni créer ni publier d'événement."""
    return bool(getattr(settings, "SUBSCRIPTION_REQUIRED", False))


def active_until(user):
    """Date de fin de l'abonnement en cours, ou None."""
    last = user.subscriptions.filter(is_paid=True, ends_at__gt=timezone.now()).order_by("-ends_at").first()
    return last.ends_at if last else None


def is_active(user):
    return active_until(user) is not None


def can_publish(user):
    return (not required()) or is_active(user)


def activate(subscription, *, provider_ref=""):
    """Active l'abonnement payé. Idempotent. Un renouvellement s'ajoute à la fin de la période en cours."""
    with transaction.atomic():
        sub = Subscription.objects.select_for_update().get(pk=subscription.pk)
        if not sub.is_paid:
            now = timezone.now()
            start = max(now, active_until(sub.user) or now)
            sub.is_paid, sub.starts_at, sub.ends_at = True, start, start + timedelta(days=sub.days)
            if provider_ref:
                sub.provider_ref = provider_ref
            sub.save(update_fields=["is_paid", "starts_at", "ends_at", "provider_ref"])
    return sub


def start_payment(user, method, phone, callback_url, request=None):
    """Lance le paiement avec le moyen choisi.

    - MTN MoMo / Moov Money (zone FCFA) : transaction PENDING + push USSD, activation par le webhook -> renvoie la Transaction.
    - Tous les autres moyens (Orange, Wave, carte, PayPal, virement…) : passerelle simulée `process_payment`
      (à remplacer par FedaPay / KkiaPay / CinetPay / Stripe) -> activation immédiate -> renvoie l'abonnement.
    """
    from core.payments import process_payment
    from payments.models import Transaction
    from payments.services import PaymentError, create_transaction, generate_reference, launch_push

    from payments import fedapay
    if fedapay.enabled():
        pending = Transaction.objects.filter(subscription__user=user, provider=Transaction.Provider.FEDAPAY,
                                             status=Transaction.Status.PENDING).exclude(checkout_url="").first()
        if pending and (timezone.now() - pending.created_at).total_seconds() < 1800:
            return pending
        sub = Subscription.objects.create(user=user, price=price(), days=duration_days(), method_key="fedapay",
                                          method_label="FedaPay", reference="pending")
        tx = fedapay.start_checkout(request, user=user, amount=sub.price, description="Abonnement organisateur", subscription=sub)
        sub.reference = tx.reference
        sub.save(update_fields=["reference"])
        return tx

    if method["provider"]:
        pending = Transaction.objects.filter(subscription__user=user, status=Transaction.Status.PENDING).first()
        if pending and (timezone.now() - pending.created_at).total_seconds() < 300:
            return pending
        sub = Subscription.objects.create(user=user, price=price(), days=duration_days(), method_key=method["key"],
                                          method_label=method["label"], reference="pending")
        tx = create_transaction(user_email=user.email, phone_number=phone, amount=sub.price, provider=method["provider"],
                                subscription=sub, country=user.country)
        sub.reference = tx.reference
        sub.save(update_fields=["reference"])
        launch_push(tx, callback_url)
        return tx

    ok, provider_ref, message = process_payment(method, phone, price())
    if not ok:
        raise PaymentError(message)
    sub = Subscription.objects.create(user=user, price=price(), days=duration_days(), method_key=method["key"],
                                      method_label=method["label"], reference=generate_reference())
    sub = activate(sub, provider_ref=provider_ref)
    transaction.on_commit(lambda: send_receipt(sub))
    return sub


def receipt_data(sub):
    return {
        "reference": sub.reference, "date": sub.starts_at or sub.created_at, "thanks": "Merci pour votre abonnement !", "event": None,
        "spectator": [("Email", sub.user.email), ("Téléphone", sub.user.phone or "—")],
        "details_title": "Détails du paiement",
        "details": [("Objet", f"Abonnement organisateur ({sub.days} jours)"), ("Référence", sub.reference),
                    ("Moyen de paiement", sub.method_label or "—"), ("Valable jusqu'au", sub.ends_at.strftime("%d/%m/%Y") if sub.ends_at else "—"),
                    ("Réf. opérateur", sub.provider_ref or "—")],
        "status": "Payé", "total": int(sub.price), "signature": None, "organizer": None, "qr": None,
    }


def send_receipt(sub):
    """Reçu e-mail (+ PDF) pour un abonnement payé hors push Mobile Money. Un reçu raté n'annule jamais le paiement."""
    from core.pdf import render_receipt
    from orders.services import build_receipt_email

    try:
        data = receipt_data(sub)
        msg = build_receipt_email(data, to=sub.user.email, subject=f"Votre reçu {settings.PLATFORM_NAME} — {sub.reference}",
                                  attachments=[(f"recu-{sub.reference}.pdf", render_receipt(data))])
        msg.send(fail_silently=True)
    except Exception:
        logger.exception("Envoi du reçu d'abonnement impossible (%s)", sub.reference)
