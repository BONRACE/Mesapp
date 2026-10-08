"""Logique métier : commandes, paiement, commission, QR codes, billets PDF, reçu e-mail, retraits."""
import io
import secrets
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import qrcode
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Sum
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

from core.payments import find_method, process_payment
from events.models import TicketType

from .models import Order, Ticket, Withdrawal

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_PER_ORDER = 10
GREEN = (21, 128, 61)


class PurchaseError(Exception):
    """Erreur métier affichable à l'utilisateur."""


def make_reference(prefix="NT", length=8):
    return f"{prefix}-" + "".join(secrets.choice(ALPHABET) for _ in range(length))


def compute_amounts(total):
    pct = Decimal(settings.PLATFORM_COMMISSION_PERCENT)
    commission = int((Decimal(total) * pct / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return commission, total - commission


@transaction.atomic
def create_order(buyer, ticket_type, quantity):
    event = ticket_type.event
    if event.organizer_id == buyer.id:
        raise PurchaseError("Vous ne pouvez pas acheter de billets pour votre propre événement.")
    if not event.is_published:
        raise PurchaseError("Cet événement n'est pas ouvert à la vente.")
    if event.sales_closed:
        raise PurchaseError("La vente des billets est terminée pour cet événement.")
    if quantity < 1 or quantity > MAX_PER_ORDER:
        raise PurchaseError(f"Vous pouvez acheter entre 1 et {MAX_PER_ORDER} billets par commande.")
    if ticket_type.remaining < quantity:
        raise PurchaseError(f"Il ne reste que {ticket_type.remaining} billet(s) de ce type.")
    total = ticket_type.price * quantity
    commission, net = compute_amounts(total)
    return Order.objects.create(
        reference=make_reference("CMD"), buyer=buyer, event=event, ticket_type=ticket_type,
        quantity=quantity, unit_price=ticket_type.price, total=total,
        commission=commission, organizer_amount=net,
    )


def pay_order(order, method_key, phone, send_email=True):
    """Paiement (simulé) d'une commande. Renvoie (order, ok, message)."""
    method = find_method(order.buyer.country, method_key)
    if method is None:
        raise PurchaseError("Moyen de paiement indisponible dans votre pays.")
    if method["kind"] == "momo" and len("".join(c for c in phone if c.isdigit())) < 8:
        raise PurchaseError("Saisissez le numéro Mobile Money à débiter.")
    if order.buyer_id == order.event.organizer_id:
        raise PurchaseError("Vous ne pouvez pas acheter de billets pour votre propre événement.")

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == Order.Status.PAID:
            return order, True, "Commande déjà payée."
        tt = TicketType.objects.select_for_update().get(pk=order.ticket_type_id)
        if tt.remaining < order.quantity:
            raise PurchaseError("Stock épuisé entre-temps : il ne reste plus assez de billets.")
        if order.event.sales_closed:
            raise PurchaseError("La vente des billets est terminée.")
        ok, provider_ref, message = process_payment(method, phone, order.total)
        if not ok:
            return order, False, message
        order.status = Order.Status.PAID
        order.paid_at = timezone.now()
        order.payment_method = method["key"]
        order.payment_label = method["label"]
        order.payment_phone = phone
        order.payment_ref = provider_ref
        order.save()
        for _ in range(order.quantity):
            Ticket.objects.create(order=order, reference=make_reference("TK", 10))
    if send_email:
        send_receipt(order)
    return order, True, message


# ----------------------------------------------------------------------------- retraits

def organizer_balance(user):
    earned = Order.objects.filter(event__organizer=user, status=Order.Status.PAID).aggregate(s=Sum("organizer_amount"))["s"] or 0
    withdrawn = Withdrawal.objects.filter(organizer=user).aggregate(s=Sum("amount"))["s"] or 0
    return earned - withdrawn


@transaction.atomic
def request_withdrawal(user, amount, method_key, phone):
    method = find_method(user.country, method_key, payout=True)
    if method is None:
        raise PurchaseError("Moyen de retrait indisponible dans votre pays.")
    if amount < settings.MIN_WITHDRAWAL:
        raise PurchaseError(f"Le retrait minimum est de {settings.MIN_WITHDRAWAL} {settings.CURRENCY}.")
    if amount > organizer_balance(user):
        raise PurchaseError("Montant supérieur à votre solde disponible.")
    if not phone.strip():
        raise PurchaseError("Indiquez le numéro ou le compte de réception.")
    return Withdrawal.objects.create(
        organizer=user, amount=amount, method=method["key"], method_label=method["label"], phone=phone.strip(),
    )


# ----------------------------------------------------------------------------- QR code

def verify_url(ticket):
    return settings.SITE_URL.rstrip("/") + reverse("core:verify", args=[ticket.reference])


def qr_png(data):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=GREEN),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ----------------------------------------------------------------------------- PDF

def ticket_pdf(ticket):
    """Billet « boarding pass » au format PDF (paysage)."""
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas

    order, event, user = ticket.order, ticket.order.event, ticket.order.buyer
    W, H = 210 * mm, 90 * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Billet {ticket.reference}")
    green, dark, grey = HexColor("#16a34a"), HexColor("#14532d"), HexColor("#6b7280")

    def img(path_or_bytes, x, y, w, h):
        try:
            src = io.BytesIO(path_or_bytes) if isinstance(path_or_bytes, bytes) else str(path_or_bytes)
            c.drawImage(ImageReader(src), x, y, w, h, preserveAspectRatio=True, anchor="c", mask="auto")
        except Exception:
            pass

    def fit(text, font, size, max_w):
        while stringWidth(text, font, size) > max_w and len(text) > 4:
            text = text[:-2]
        return text

    # fond + cadre
    c.setFillColor(HexColor("#f0fdf4"))
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setStrokeColor(green)
    c.setLineWidth(1.2)
    c.roundRect(4 * mm, 4 * mm, W - 8 * mm, H - 8 * mm, 5 * mm, fill=1, stroke=1)

    # bandeau
    c.saveState()
    p = c.beginPath()
    p.roundRect(4 * mm, H - 22 * mm, W - 8 * mm, 18 * mm, 5 * mm)
    c.clipPath(p, stroke=0)
    c.setFillColor(green)
    c.rect(4 * mm, H - 22 * mm, W - 8 * mm, 18 * mm, fill=1, stroke=0)
    c.restoreState()
    c.setFillColor(green)
    c.rect(4 * mm, H - 22 * mm, W - 8 * mm, 9 * mm, fill=1, stroke=0)  # recouvre les coins bas arrondis
    logo = Path(settings.BASE_DIR, "static/img/logo.png")
    c.setFillColor(white)
    c.circle(17 * mm, H - 13 * mm, 6.5 * mm, fill=1, stroke=0)
    img(logo, 11.5 * mm, H - 18.5 * mm, 11 * mm, 11 * mm)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(27 * mm, H - 12 * mm, settings.PLATFORM_NAME.upper())
    c.setFont("Helvetica", 7.5)
    c.drawString(27 * mm, H - 16.5 * mm, "BOARDING PASS  ·  BILLET D'ENTRÉE")
    org_logo = event.logo_or_none
    if org_logo:
        c.setFillColor(white)
        c.circle(W - 17 * mm, H - 13 * mm, 6.5 * mm, fill=1, stroke=0)
        img(org_logo.path, W - 22.5 * mm, H - 18.5 * mm, 11 * mm, 11 * mm)

    # séparation pointillée
    sep = 148 * mm
    c.setDash(2, 2)
    c.setStrokeColor(HexColor("#86efac"))
    c.line(sep, 8 * mm, sep, H - 24 * mm)
    c.setDash()

    # nom de l'événement
    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(12 * mm, H - 32 * mm, fit(event.name, "Helvetica-Bold", 16, sep - 24 * mm))

    # photo
    px, py, ps = 12 * mm, 18 * mm, 32 * mm
    c.setStrokeColor(green)
    c.setLineWidth(1)
    if user.photo:
        img(user.photo.path, px, py, ps, ps)
        c.rect(px, py, ps, ps, fill=0, stroke=1)
    else:
        c.setFillColor(HexColor("#dcfce7"))
        c.rect(px, py, ps, ps, fill=1, stroke=1)
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", 24)
        c.drawCentredString(px + ps / 2, py + ps / 2 - 4 * mm, user.initials)

    # champs
    def field(x, y, label, value, size=10.5, max_w=46 * mm):
        c.setFillColor(grey)
        c.setFont("Helvetica", 6.5)
        c.drawString(x, y + 5 * mm, label.upper())
        c.setFillColor(dark)
        c.setFont("Helvetica-Bold", size)
        c.drawString(x, y, fit(value, "Helvetica-Bold", size, max_w))

    x1, x2 = 50 * mm, 100 * mm
    field(x1, H - 43 * mm, "Nom & prénoms", user.ticket_name, 11, 92 * mm)
    field(x1, H - 54 * mm, "Sexe", user.get_sexe_display() or "—")
    field(x2, H - 54 * mm, "Type de ticket", ticket.order.ticket_type.name, 10.5, 44 * mm)
    field(x1, H - 65 * mm, "Date", event.start_date.strftime("%d/%m/%Y"))
    field(x2, H - 65 * mm, "Heure", event.start_time.strftime("%H:%M"))
    field(x1, H - 76 * mm, "Lieu", event.location, 10, 92 * mm)

    # talon : QR code
    img(qr_png(verify_url(ticket)), sep + 10 * mm, 25 * mm, 40 * mm, 40 * mm)
    c.setFillColor(dark)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(sep + 30 * mm, 21 * mm, ticket.reference)
    c.setFillColor(grey)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(sep + 30 * mm, 16.5 * mm, "Présentez ce QR code à l'entrée")
    c.showPage()
    c.save()
    return buf.getvalue()


# ----------------------------------------------------------------------------- e-mail reçu

class ReceiptEmail(EmailMultiAlternatives):
    """E-mail HTML avec images intégrées (multipart/related) + billets PDF en pièces jointes.

    Django 6 ne gère plus `mixed_subtype` : on construit donc la partie HTML « related » nous-mêmes.
    """

    inline_images = ()  # [(cid, bytes_png), ...]

    def _add_bodies(self, msg):
        msg.set_content(self.body, charset="utf-8")
        msg.make_alternative()
        msg.add_alternative(self.alternatives[0].content, subtype="html", charset="utf-8")
        html_part = msg.get_payload()[-1]
        for cid, data in self.inline_images:
            html_part.add_related(data, "image", "png", cid=f"<{cid}>", filename=f"{cid}.png", disposition="inline")
        return msg


def send_receipt(order):
    """Reçu e-mail automatique après un paiement validé (modèle fourni dans la maquette)."""
    event, buyer = order.event, order.buyer
    first = order.tickets.first()
    ctx = {"order": order, "event": event, "buyer": buyer, "ticket": first, "platform": settings.PLATFORM_NAME,
           "currency": settings.CURRENCY, "organizer": event.organizer, "tickets": order.tickets.all()}
    html = render_to_string("emails/receipt.html", ctx)
    text = render_to_string("emails/receipt.txt", ctx)
    platform_logo = Path(settings.BASE_DIR, "static/img/logo.png").read_bytes()
    ev_logo = event.logo_or_none
    images = [("logo", platform_logo), ("eventlogo", Path(ev_logo.path).read_bytes() if ev_logo else platform_logo)]
    if first:
        images.append(("qr", qr_png(verify_url(first))))

    msg = ReceiptEmail(
        subject=f"Votre reçu {settings.PLATFORM_NAME} — {event.name}", body=text,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[buyer.email],
    )
    msg.attach_alternative(html, "text/html")
    msg.inline_images = images
    for t in order.tickets.all():
        msg.attach(f"billet-{t.reference}.pdf", ticket_pdf(t), "application/pdf")
    msg.send(fail_silently=True)
