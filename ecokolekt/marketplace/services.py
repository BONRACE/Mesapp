"""Règles métier du marché : réservation de stock, calcul de commission, cycle de vie des commandes."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Listing, Order


def compute_amounts(quantity_kg, unit_price_xof):
    """Retourne (sous-total, commission, versement vendeur) en XOF entiers."""
    subtotal = int((Decimal(quantity_kg) * unit_price_xof).quantize(Decimal("1"), ROUND_HALF_UP))
    commission = int((Decimal(subtotal) * settings.PLATFORM_COMMISSION_RATE).quantize(Decimal("1"), ROUND_HALF_UP))
    return subtotal, commission, subtotal - commission


class OutOfStock(Exception):
    pass


def create_order(buyer, listing_id, quantity_kg):
    """Réserve le stock et crée la commande en attente de paiement (verrou pessimiste)."""
    with transaction.atomic():
        listing = Listing.objects.select_for_update().get(pk=listing_id, status=Listing.Status.ACTIVE)
        if listing.seller_id == buyer.pk:
            raise ValueError("Vous ne pouvez pas acheter votre propre offre.")
        if Decimal(quantity_kg) > listing.available_kg:
            raise OutOfStock(f"Stock disponible : {listing.available_kg} kg.")
        listing.available_kg -= Decimal(quantity_kg)
        if listing.available_kg == 0:
            listing.status = Listing.Status.SOLD_OUT
        listing.save(update_fields=["available_kg", "status"])
        subtotal, commission, payout = compute_amounts(quantity_kg, listing.price_per_kg_xof)
        return Order.objects.create(
            buyer=buyer,
            listing=listing,
            quantity_kg=quantity_kg,
            unit_price_xof=listing.price_per_kg_xof,
            subtotal_xof=subtotal,
            commission_xof=commission,
            seller_payout_xof=payout,
        )


def mark_paid(order):
    """Passe une commande à « payée ». Idempotent.

    À appeler depuis le webhook de paiement (FedaPay) une fois le paiement confirmé.
    """
    if order.status == Order.Status.PAID:
        return order
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=["status", "paid_at"])
    return order


def cancel_order(order):
    """Annule une commande non payée et rend le stock à l'offre."""
    if order.status != Order.Status.PENDING_PAYMENT:
        return order
    with transaction.atomic():
        listing = Listing.objects.select_for_update().get(pk=order.listing_id)
        listing.available_kg += order.quantity_kg
        if listing.status == Listing.Status.SOLD_OUT:
            listing.status = Listing.Status.ACTIVE
        listing.save(update_fields=["available_kg", "status"])
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status"])
    return order
