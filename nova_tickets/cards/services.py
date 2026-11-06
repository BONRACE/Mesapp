"""Cartes de visite : activation (gratuite ou payée en Mobile Money), fichier vCard, QR code."""
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BusinessCard


def linked_ticket(card, reference):
    """Billet PAYÉ appartenant au propriétaire de la carte (sinon None) : garantit que le badge « Participant »
    affiché sur la carte publique correspond à un vrai billet de cette personne."""
    if not reference or not card.is_active:
        return None
    from orders.models import Order, Ticket
    return (Ticket.objects.select_related("order__event")
            .filter(reference=reference.strip().upper(), order__buyer=card.user, order__status=Order.Status.PAID).first())


def card_price():
    return int(getattr(settings, "BUSINESS_CARD_PRICE", 0))


def activate_card(card):
    """Active la carte. Idempotent (appelé par le webhook de paiement, qui peut être rejoué)."""
    with transaction.atomic():
        card = BusinessCard.objects.select_for_update().get(pk=card.pk)
        if not card.is_active:
            card.is_active, card.activated_at = True, timezone.now()
            card.save(update_fields=["is_active", "activated_at", "updated_at"])
    return card


def start_activation(card, provider, phone, callback_url, request=None):
    """Active tout de suite si la carte est gratuite, sinon lance un paiement MTN / Moov.

    Renvoie la Transaction à suivre, ou None si la carte a été activée directement.
    """
    price = card_price()
    if price <= 0:
        activate_card(card)
        return None

    from payments.models import Transaction
    from payments.services import create_transaction, launch_push

    from payments import fedapay
    pending = card.transactions.filter(status=Transaction.Status.PENDING).first()
    if pending and (timezone.now() - pending.created_at).total_seconds() < (1800 if pending.checkout_url else 300):
        return pending
    if fedapay.enabled():
        return fedapay.start_checkout(request, user=card.user, amount=price, description="Activation carte de visite", business_card=card)
    tx = create_transaction(user_email=card.user.email, phone_number=phone, amount=price, provider=provider,
                            business_card=card, country=card.user.country)
    launch_push(tx, callback_url)
    return tx


# ----------------------------------------------------------------------------- vCard

def _esc(value):
    """Échappement vCard 3.0 : \\ ; , et retours à la ligne."""
    return (value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def vcard(card):
    """Contenu .vcf (vCard 3.0, lignes CRLF) importable dans les contacts iPhone / Android / Outlook."""
    parts = card.full_name.split()
    last = parts[-1] if len(parts) > 1 else ""
    first = " ".join(parts[:-1]) if len(parts) > 1 else card.full_name
    lines = ["BEGIN:VCARD", "VERSION:3.0",
             f"N:{_esc(last)};{_esc(first)};;;", f"FN:{_esc(card.full_name)}"]
    if card.company:
        lines.append(f"ORG:{_esc(card.company)}")
    if card.job_title:
        lines.append(f"TITLE:{_esc(card.job_title)}")
    if card.phone:
        lines.append(f"TEL;TYPE=CELL,VOICE:{_esc(card.phone)}")
    if card.email:
        lines.append(f"EMAIL;TYPE=INTERNET,WORK:{_esc(card.email)}")
    if card.website:
        lines.append(f"URL:{_esc(card.website)}")
    if card.linkedin:
        lines.append(f"X-SOCIALPROFILE;TYPE=linkedin:{_esc(card.linkedin)}")
    if card.city:
        lines.append(f"ADR;TYPE=WORK:;;;{_esc(card.city)};;;")
    if card.bio:
        lines.append(f"NOTE:{_esc(card.bio)}")
    lines += [f"X-NOVATICKETS-CARD:{_esc(card.public_url)}", "END:VCARD"]
    return "\r\n".join(lines) + "\r\n"
