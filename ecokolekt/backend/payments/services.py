from django.db import transaction

from marketplace.models import Order
from marketplace.services import MarketError, expire_stale_orders, mark_paid

from .models import Payment
from .providers import ProviderError, get_provider


def initiate_payment(order_id, user, method=Payment.Method.MOBILE_MONEY) -> Payment:
    expire_stale_orders()
    order = Order.objects.filter(pk=order_id, buyer=user).first()
    if not order:
        raise MarketError("Commande introuvable.", 404)
    if order.status != Order.Status.PENDING_PAYMENT:
        raise MarketError("Cette commande n'est plus à payer.", 409)
    provider = get_provider()
    payment = Payment.objects.create(order=order, payer=user, provider=provider.name, method=method, amount=order.total)
    try:
        info = provider.create(payment, order, user)
    except ProviderError:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        raise
    payment.provider_ref, payment.checkout_url = info["provider_ref"], info["checkout_url"]
    payment.save(update_fields=["provider_ref", "checkout_url", "updated_at"])
    return payment


def finalize_payment(payment_id, outcome: str) -> Payment:
    """Applique un résultat (« succeeded » / « failed »). Idempotent : un paiement réussi ne change plus."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if payment.status == Payment.Status.SUCCEEDED or outcome == Payment.Status.PENDING:
            return payment
        if outcome == Payment.Status.FAILED:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])
            return payment
        payment.status = Payment.Status.SUCCEEDED
        _, stock_refund = mark_paid(payment.order_id)
        duplicate = Payment.objects.filter(order_id=payment.order_id, status=Payment.Status.SUCCEEDED).exclude(pk=payment.pk).exists()
        payment.needs_refund = stock_refund or duplicate
        payment.save(update_fields=["status", "needs_refund", "updated_at"])
        return payment


def refresh_payment(payment: Payment) -> Payment:
    """Réconciliation : interroge la passerelle (utile si le webhook est perdu ou en retard)."""
    if payment.status != Payment.Status.PENDING or payment.provider == "mock":
        return payment
    try:
        outcome = get_provider(payment.provider).fetch_status(payment)
    except ProviderError:
        return payment
    return finalize_payment(payment.pk, outcome)
