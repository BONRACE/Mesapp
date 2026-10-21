"""Création des commandes et émission des tickets."""
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from events.models import TicketType
from payments.services import complete_payment, create_payment
from payments.signals import FulfilmentError

from .models import Order, Ticket


def compute_commission(total: int) -> int:
    pct = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))
    return int((Decimal(total) * pct / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def check_can_buy(user, ticket_type: TicketType, quantity: int):
    """Règles d'achat ; lève ValidationError avec un message en français."""
    event = ticket_type.event
    if event.organizer_id == user.id:
        raise ValidationError("Vous ne pouvez pas acheter de tickets pour votre propre événement.")
    if not event.sales_open:
        raise ValidationError("Les ventes sont fermées pour cet événement.")
    if not 1 <= quantity <= settings.MAX_TICKETS_PER_ORDER:
        raise ValidationError(f"Vous pouvez commander de 1 à {settings.MAX_TICKETS_PER_ORDER} tickets à la fois.")
    if ticket_type.remaining < quantity:
        raise ValidationError(
            "Ce type de ticket est épuisé." if ticket_type.sold_out
            else f"Il ne reste que {ticket_type.remaining} ticket(s) de ce type."
        )


def create_order(user, ticket_type: TicketType, quantity: int, recipient=None):
    """Crée la commande (en attente) et le paiement associé. `recipient` : dict pour un ami."""
    check_can_buy(user, ticket_type, quantity)
    total = ticket_type.price * quantity
    recipient = recipient or {}
    with transaction.atomic():
        order = Order.objects.create(
            buyer=user, event=ticket_type.event, ticket_type=ticket_type, quantity=quantity,
            unit_price=ticket_type.price, total=total, commission=compute_commission(total),
            is_gift=bool(recipient),
            recipient_first_name=recipient.get("first_name", ""),
            recipient_last_name=recipient.get("last_name", ""),
            recipient_email=recipient.get("email", ""),
            recipient_phone=recipient.get("phone", ""),
            recipient_sexe=recipient.get("sexe", ""),
            recipient_photo=recipient.get("photo") or "",
        )
        payment = create_payment(user, "ticket", total, order=order)
    if total == 0:  # ticket gratuit : pas de passerelle
        payment.method = "free"
        payment.save(update_fields=["method"])
        payment = complete_payment(payment)
    return order, payment


def issue_tickets(payment):
    """Récepteur de `payment_succeeded` : marque la commande payée et émet les tickets."""
    if not payment.order_id:
        return
    order = Order.objects.select_for_update().select_related("buyer", "ticket_type", "event").get(pk=payment.order_id)
    if order.status == Order.Status.PAID:
        return
    ttype = TicketType.objects.select_for_update().get(pk=order.ticket_type_id)
    if ttype.remaining < order.quantity:
        order.status = Order.Status.FAILED
        order.save(update_fields=["status"])
        raise FulfilmentError("Stock épuisé pendant le paiement.")
    ttype.sold += order.quantity
    ttype.save(update_fields=["sold"])

    buyer = order.buyer
    for i in range(order.quantity):
        if order.is_gift:
            holder = dict(holder_first_name=order.recipient_first_name, holder_last_name=order.recipient_last_name,
                          holder_email=order.recipient_email, holder_phone=order.recipient_phone,
                          holder_sexe=order.recipient_sexe, holder_photo=order.recipient_photo)
        else:
            holder = dict(holder_first_name=buyer.first_name, holder_last_name=buyer.last_name,
                          holder_email=buyer.email, holder_phone=buyer.phone, holder_sexe=buyer.sexe)
        Ticket.objects.create(order=order, **holder)
    order.status, order.paid_at = Order.Status.PAID, timezone.now()
    order.save(update_fields=["status", "paid_at"])
