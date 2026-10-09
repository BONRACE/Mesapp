"""Paiement (simulé), QR code stylisé, PDF du billet et e-mail reçu."""
import io
from pathlib import Path

import qrcode
from django.conf import settings
from email.mime.image import MIMEImage

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import Order, Ticket

GREEN = HexColor("#059669")
DARK = HexColor("#0f172a")
GREY = HexColor("#64748b")


# ---------------------------------------------------------------- paiement
class PaymentError(Exception):
    pass


def charge(order, method, phone):
    """Point d'intégration d'un agrégateur (FedaPay, KkiaPay, CinetPay…).

    Ici : simulation. Un numéro se terminant par « 0000 » simule un échec.
    Remplacez le corps de cette fonction par l'appel réel à l'API.
    """
    if phone.endswith("0000"):
        raise PaymentError("Le paiement a été refusé par l'opérateur.")
    return True


def confirm_payment(order, method, phone):
    if order.status == Order.PAID:
        return order
    # 1) Débit : hors transaction, pour que le statut « échoué » reste enregistré.
    try:
        charge(order, method, phone)
    except PaymentError:
        order.status = Order.FAILED
        order.save(update_fields=["status"])
        raise
    # 2) Stock + création des billets : atomique.
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status == Order.PAID:
            return order
        if order.ticket_type.remaining < order.quantity:
            raise PaymentError("Il ne reste plus assez de tickets pour cette catégorie.")
        order.payment_method = method
        order.payment_phone = phone
        order.status = Order.PAID
        order.compute_amounts()
        order.save()
        for n in range(1, order.quantity + 1):
            Ticket.objects.create(order=order, number=n)
    return order


# ---------------------------------------------------------------- QR code
def qr_png(data: str) -> bytes:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=(5, 150, 105)),
    )
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- PDF
def _img(field_or_path):
    try:
        if hasattr(field_or_path, "path"):
            return ImageReader(field_or_path.path) if field_or_path else None
        return ImageReader(str(field_or_path))
    except Exception:
        return None


def ticket_pdf(ticket: Ticket) -> bytes:
    order, event, user = ticket.order, ticket.order.event, ticket.order.user
    W, H = 760, 300
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f"Billet {ticket.short_code}")

    # fond + carte
    c.setFillColor(HexColor("#ecfdf5"))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(white)
    c.roundRect(15, 15, W - 30, H - 30, 18, stroke=0, fill=1)

    # bandeau vert gauche
    c.setFillColor(GREEN)
    c.roundRect(15, H - 75, W - 30, 60, 18, stroke=0, fill=1)
    c.rect(15, H - 75, W - 30, 30, stroke=0, fill=1)

    # logo NovaTickets sur pastille blanche (lisible sur le bandeau vert)
    c.setFillColor(white)
    c.roundRect(28, H - 71, 128, 52, 10, stroke=0, fill=1)
    logo = _img(Path(settings.BASE_DIR) / "static/img/logo-horizontal.png")
    if logo:
        c.drawImage(logo, 36, H - 66, width=112, height=42, mask="auto", preserveAspectRatio=True)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(170, H - 50, "BOARDING PASS")

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(W - 220, H - 52, ticket.order.ticket_type.name.upper())

    # logo organisateur / événement
    ev_logo = _img(event.logo) if event.logo else _img(event.organizer.org_logo) if event.organizer.org_logo else None
    if ev_logo:
        c.drawImage(ev_logo, 320, H - 68, width=46, height=46, mask="auto", preserveAspectRatio=True)

    # photo spectateur
    ph = _img(order.holder_photo) if order.holder_photo else None
    if ph:
        c.drawImage(ph, 35, 60, width=90, height=110, preserveAspectRatio=True, mask="auto")
    else:
        c.setFillColor(HexColor("#d1fae5"))
        c.roundRect(35, 60, 90, 110, 8, stroke=0, fill=1)
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 40)
        c.drawCentredString(80, 100, order.holder_initial)

    # infos
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8)
    c.drawString(145, 190, "ÉVÉNEMENT")
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(145, 170, event.name[:42])

    def field(x, y, label, value):
        c.setFillColor(GREY)
        c.setFont("Helvetica", 8)
        c.drawString(x, y + 14, label)
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y, str(value)[:30])

    field(145, 135, "NOM", order.holder_last_name.upper() or "-")
    field(145, 100, "PRÉNOMS", order.holder_first_name or "-")
    field(310, 135, "SEXE", order.holder_sexe_display)
    field(310, 100, "DATE", f"{event.start_date:%d/%m/%Y} · {event.start_time:%Hh%M}")
    field(145, 65, "LIEU", event.location or "-")
    field(310, 65, "TICKET", f"{order.reference}-{ticket.number}")

    # ligne pointillée
    c.setStrokeColor(HexColor("#a7f3d0"))
    c.setDash(4, 4)
    c.line(W - 190, 30, W - 190, H - 80)
    c.setDash()

    # QR
    qr = ImageReader(io.BytesIO(qr_png(ticket.verify_url())))
    c.drawImage(qr, W - 175, 75, width=140, height=140)
    c.setFillColor(GREY)
    c.setFont("Helvetica", 8)
    c.drawCentredString(W - 105, 62, f"CODE {ticket.short_code}")
    c.setFont("Helvetica", 7)
    c.drawCentredString(W - 105, 46, "Présentez ce QR code à l'entrée")

    c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------- e-mail
def _read(field):
    try:
        with open(field.path, "rb") as fh:
            return fh.read()
    except Exception:
        return None


def _inline(msg, cid, data, subtype="png"):
    """Image intégrée au message (affichée même si le site n'est pas en ligne)."""
    if not data:
        return False
    img = MIMEImage(data, _subtype=subtype)
    img.add_header("Content-ID", f"<{cid}>")
    img.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
    msg.attach(img)
    return True


def _logo_bytes(name):
    with open(Path(settings.BASE_DIR) / "static/img" / name, "rb") as fh:
        return fh.read()


def _social_links():
    return [(n, u) for n, u in getattr(settings, "SOCIAL_LINKS", {}).items() if u]


def _build(subject, to, template, ctx, order, text):
    first = order.tickets.first()
    event = order.event
    msg = EmailMultiAlternatives(subject=subject, body=text, from_email=settings.DEFAULT_FROM_EMAIL, to=to)
    msg.mixed_subtype = "related"
    ev_logo = event.logo or event.organizer.org_logo
    ctx = dict(ctx)
    ctx.update({
        "order": order, "event": event, "organizer": event.organizer,
        "tickets_url": f"{settings.SITE_URL}/mes-billets/",
        "social_links": _social_links(),
        "has_event_logo": bool(ev_logo and _inline(msg, "eventlogo", _read(ev_logo), "png")),
        "has_qr": bool(first and _inline(msg, "qrcode", qr_png(first.verify_url()))),
    })
    _inline(msg, "logo", _logo_bytes("logo-full.png"))
    msg.attach_alternative(render_to_string(template, ctx), "text/html")
    return msg


def send_receipt(order: Order):
    """Reçu envoyé à l'acheteur après un paiement validé."""
    user, event = order.user, order.event
    text = (
        f"Merci pour votre achat, {user.first_name} !\n"
        f"Événement : {event.name}\nRéférence : {order.reference}\n"
        f"Ticket : {order.ticket_type.name} x{order.quantity}\nTotal : {order.total} FCFA\n"
    )
    if order.for_friend:
        text += f"Billet offert à : {order.holder_name}\n"
    text += f"Vos billets : {settings.SITE_URL}/mes-billets/"
    msg = _build(f"Votre reçu NovaTickets – {event.name}", [user.email], "emails/receipt.html",
                 {"user": user}, order, text)
    msg.send(fail_silently=True)
    if order.for_friend and order.friend_email:
        send_friend_ticket(order)


def send_friend_ticket(order: Order):
    """Billet(s) en PDF envoyé(s) à l'ami bénéficiaire."""
    event, buyer = order.event, order.user
    text = (
        f"Bonjour {order.holder_first_name},\n{buyer.display_name} vous offre un billet pour {event.name} "
        f"({event.start_date:%d/%m/%Y} à {event.start_time:%Hh%M}).\n"
        "Votre billet est en pièce jointe : présentez son QR code à l'entrée."
    )
    msg = _build(f"{buyer.display_name} vous offre un billet – {event.name}", [order.friend_email],
                 "emails/friend_ticket.html", {"buyer": buyer}, order, text)
    for t in order.tickets.all():
        msg.attach(f"billet-{t.short_code}.pdf", ticket_pdf(t), "application/pdf")
    msg.send(fail_silently=True)
