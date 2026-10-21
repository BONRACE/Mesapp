"""E-mail de reçu envoyé automatiquement dès qu'un paiement est validé."""
import io
import logging
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from core.countries import format_phone

from .emailimages import signature_png, stamp_png
from .pdf import tickets_pdf
from .qr import qr_png, ticket_url

log = logging.getLogger(__name__)
STATIC = settings.BASE_DIR / "static"


def _read(path):
    try:
        return open(path, "rb").read()
    except (OSError, ValueError):
        return None


def _inline_images(order):
    """Images intégrées au mail (Content-ID), plus fiables que des liens distants."""
    event, org = order.event, order.event.organizer
    images = {
        "platform_logo": _read(STATIC / "img" / "logo.png"),
        "signature": signature_png(org.display_org),
        "stamp": stamp_png(),
    }
    logo_file = event.logo or org.organisation_logo
    if logo_file:
        images["event_logo"] = _read(logo_file.path)
    first = order.tickets.first()
    if first:
        images["qr"] = qr_png(ticket_url(first), 6, False)
    return {k: v for k, v in images.items() if v}


def _build(order, payment, to_email, *, holder=None, gift_from=None):
    """Construit le message ; `holder` = bénéficiaire (mail destiné à l'ami)."""
    buyer = order.buyer
    who = holder or {
        "last_name": buyer.last_name, "first_name": buyer.first_name,
        "email": buyer.email, "phone": format_phone(buyer.phone),
    }
    images = _inline_images(order)
    ctx = {
        "order": order, "event": order.event, "payment": payment, "who": who, "gift_from": gift_from,
        "organizer": order.event.organizer, "date": timezone.localtime(payment.completed_at or timezone.now()),
        "tickets": list(order.tickets.all()), "cid": {k: f"{k}@novatickets" for k in images},
        "site_url": settings.SITE_URL, "platform": settings.PLATFORM_NAME,
        "verify_url": ticket_url(order.tickets.first()) if order.tickets.exists() else settings.SITE_URL,
    }
    html = render_to_string("emails/receipt.html", ctx)
    text = render_to_string("emails/receipt.txt", ctx)
    subject = (
        f"Votre ticket offert par {gift_from} — {order.event.name}" if gift_from
        else f"Merci pour votre achat ! Reçu {order.reference} — {order.event.name}"
    )
    msg = EmailMultiAlternatives(subject, text or strip_tags(html), settings.DEFAULT_FROM_EMAIL, [to_email])
    msg.attach_alternative(html, "text/html")
    msg.mixed_subtype = "related"  # permet les images « cid: » dans le HTML
    for key, data in images.items():
        part = MIMEImage(data, _subtype="png")
        part.add_header("Content-ID", f"<{ctx['cid'][key]}>")
        part.add_header("Content-Disposition", "inline", filename=f"{key}.png")
        msg.attach(part)
    msg.attach(f"tickets-{order.reference}.pdf", tickets_pdf(order.tickets.all()), "application/pdf")
    return msg


def send_receipt(order, payment):
    """Envoie le reçu à l'acheteur (et le ticket à l'ami en cas de réservation pour un ami)."""
    sent = 0
    _build(order, payment, order.buyer.email).send()
    sent += 1
    if order.is_gift and order.recipient_email and order.recipient_email.lower() != order.buyer.email.lower():
        holder = {
            "last_name": order.recipient_last_name, "first_name": order.recipient_first_name,
            "email": order.recipient_email, "phone": format_phone(order.recipient_phone) if order.recipient_phone else "—",
        }
        try:
            _build(order, payment, order.recipient_email, holder=holder, gift_from=order.buyer.full_name).send()
            sent += 1
        except Exception:
            log.exception("Envoi du ticket à l'ami impossible (commande %s)", order.pk)
    return sent
