"""Règles métier du marché. Toutes les mutations de stock passent par ici, sous verrou de ligne."""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Listing, Order, commission_for


class MarketError(Exception):
    def __init__(self, message, http_status=400):
        super().__init__(message)
        self.http_status = http_status


def place_order(buyer, listing_id, quantity_kg: Decimal, delivery_address="", notes="") -> Order:
    if not buyer.profile_completed:
        raise MarketError("Complétez votre profil avant de commander.", 403)
    with transaction.atomic():
        listing = Listing.objects.select_for_update().select_related("seller").filter(pk=listing_id).first()
        if not listing or not listing.is_active:
            raise MarketError("Annonce introuvable ou retirée.", 404)
        if listing.seller_id == buyer.id:
            raise MarketError("Vous ne pouvez pas acheter votre propre annonce.", 403)
        if quantity_kg < listing.min_order_kg:
            raise MarketError(f"Commande minimale : {listing.min_order_kg.normalize():f} kg.")
        if quantity_kg > listing.quantity_kg:
            raise MarketError(f"Stock insuffisant : {listing.quantity_kg.normalize():f} kg disponibles.", 409)
        subtotal = int((quantity_kg * listing.unit_price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        listing.quantity_kg -= quantity_kg
        listing.save(update_fields=["quantity_kg", "updated_at"])
        return Order.objects.create(
            buyer=buyer, seller=listing.seller, listing=listing, quantity_kg=quantity_kg,
            unit_price=listing.unit_price, total=subtotal, commission=commission_for(subtotal),
            delivery_address=delivery_address, notes=notes,
        )


def _release_stock(order: Order):
    listing = Listing.objects.select_for_update().get(pk=order.listing_id)
    listing.quantity_kg += order.quantity_kg
    listing.save(update_fields=["quantity_kg", "updated_at"])


def cancel_order(order_id, new_status=Order.Status.CANCELLED) -> Order:
    """Annule une commande non payée et restitue le stock. Idempotent."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status != Order.Status.PENDING_PAYMENT:
            raise MarketError("Seule une commande non payée peut être annulée.", 409)
        _release_stock(order)
        order.status = new_status
        order.save(update_fields=["status"])
    return order


def expire_stale_orders() -> int:
    cutoff = timezone.now() - timedelta(minutes=settings.ORDER_PAYMENT_TTL_MINUTES)
    ids = list(Order.objects.filter(status=Order.Status.PENDING_PAYMENT, created_at__lt=cutoff).values_list("pk", flat=True))
    n = 0
    for pk in ids:
        try:
            cancel_order(pk, Order.Status.EXPIRED)
            n += 1
        except MarketError:  # payée entre-temps
            continue
    return n


def mark_paid(order_id) -> tuple[Order, bool]:
    """Passe la commande à « payée ». Renvoie (commande, needs_refund).

    Cas limite : le paiement aboutit après l'expiration. On tente de re-réserver le stock ;
    s'il n'est plus disponible, la commande reste expirée et le paiement est signalé « à rembourser ».
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        if order.status in (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED):
            return order, False
        if order.status != Order.Status.PENDING_PAYMENT:
            listing = Listing.objects.select_for_update().get(pk=order.listing_id)
            if not listing.is_active or listing.quantity_kg < order.quantity_kg:
                return order, True
            listing.quantity_kg -= order.quantity_kg
            listing.save(update_fields=["quantity_kg", "updated_at"])
        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.save(update_fields=["status", "paid_at"])
        return order, False


def ship_order(order: Order) -> Order:
    if order.status != Order.Status.PAID:
        raise MarketError("La commande doit être payée avant l'expédition.", 409)
    order.status, order.shipped_at = Order.Status.SHIPPED, timezone.now()
    order.save(update_fields=["status", "shipped_at"])
    return order


def deliver_order(order: Order) -> Order:
    if order.status != Order.Status.SHIPPED:
        raise MarketError("La commande n'a pas été expédiée.", 409)
    order.status, order.delivered_at = Order.Status.DELIVERED, timezone.now()
    order.save(update_fields=["status", "delivered_at"])
    return order
