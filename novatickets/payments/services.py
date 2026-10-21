"""Logique métier des paiements et des retraits."""
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Payment, Withdrawal
from .providers import get_provider
from .signals import FulfilmentError, payment_succeeded


def create_payment(user, purpose, amount, order=None, card=None) -> Payment:
    return Payment.objects.create(user=user, purpose=purpose, amount=amount, order=order, business_card=card)


def process_payment(payment: Payment, method: str, phone: str) -> Payment:
    """Envoie le paiement à la passerelle et finalise s'il est accepté."""
    if payment.status in (Payment.Status.SUCCEEDED, Payment.Status.REFUNDED):
        return payment
    provider = get_provider()
    payment.method, payment.payer_phone, payment.provider = method, phone, provider.code
    payment.status, payment.failure_reason = Payment.Status.PENDING, ""
    payment.save()
    try:
        result = provider.charge(payment, method, phone)
    except Exception as exc:  # panne réseau côté passerelle, etc.
        payment.status = Payment.Status.FAILED
        payment.failure_reason = f"Erreur de la passerelle : {exc}"[:255]
        payment.save()
        return payment
    payment.provider_reference = result.provider_reference
    if result.status == "succeeded":
        return complete_payment(payment)
    if result.status == "failed":
        payment.status, payment.failure_reason = Payment.Status.FAILED, result.message[:255]
    payment.save()
    return payment


def complete_payment(payment: Payment) -> Payment:
    """Valide un paiement (idempotent) et déclenche le signal `payment_succeeded`.

    Peut aussi être appelé par le webhook d'une vraie passerelle.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status == Payment.Status.SUCCEEDED:
            return payment
        payment.status = Payment.Status.SUCCEEDED
        payment.completed_at = timezone.now()
        payment.failure_reason = ""
        payment.save()
        try:
            with transaction.atomic():  # point de sauvegarde : annule les effets si échec
                payment_succeeded.send(sender=Payment, payment=payment)
        except FulfilmentError as exc:
            payment.status = Payment.Status.REFUNDED
            payment.failure_reason = f"{exc} Montant remboursé."[:255]
            payment.save()
    return payment


# --- Soldes et retraits ------------------------------------------------------

def organizer_balance(user) -> int:
    """Solde disponible = ventes − commissions − retraits (en cours ou effectués)."""
    from tickets.models import Order

    sales = Order.objects.filter(event__organizer=user, status=Order.Status.PAID).aggregate(
        gross=Sum("total"), commission=Sum("commission")
    )
    earned = (sales["gross"] or 0) - (sales["commission"] or 0)
    withdrawn = Withdrawal.objects.filter(
        organizer=user, status__in=[Withdrawal.Status.PENDING, Withdrawal.Status.COMPLETED]
    ).aggregate(s=Sum("amount"))["s"] or 0
    return earned - withdrawn


def request_withdrawal(user, amount: int, method: str, phone: str) -> Withdrawal:
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)  # évite deux retraits simultanés
        if amount > organizer_balance(user):
            raise ValueError("Montant supérieur à votre solde disponible.")
        withdrawal = Withdrawal.objects.create(organizer=user, amount=amount, method=method, phone=phone)
        result = get_provider().payout(withdrawal)
        withdrawal.provider_reference = result.provider_reference
        if result.status == "completed":
            withdrawal.status, withdrawal.completed_at = Withdrawal.Status.COMPLETED, timezone.now()
        else:
            withdrawal.status, withdrawal.failure_reason = Withdrawal.Status.FAILED, result.message[:255]
        withdrawal.save()
    return withdrawal
