"""Logique métier : commandes, paiement, commission, QR codes, billets PDF, reçu e-mail, retraits."""
import io
import logging
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

logger = logging.getLogger(__name__)

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_PER_ORDER = 10
GREEN = (21, 128, 61)


class PurchaseError(Exception):
    """Erreur métier affichable à l'utilisateur."""


def make_reference(prefix="NT", length=8):
    return f"{prefix}-" + "".join(secrets.choice(ALPHABET) for _ in range(length))


def commission_percent(organizer=None):
    """Taux de commission applicable à une vente de cet organisateur : 0 % avec un abonnement actif, sinon le taux standard (2,5 %)."""
    if organizer is not None:
        from subscriptions.services import is_active
        if is_active(organizer):
            return Decimal("0")
    return Decimal(str(settings.PLATFORM_COMMISSION_PERCENT))


def compute_amounts(total, organizer=None):
    """(commission, part de l'organisateur). `organizer` : s'il a un abonnement actif, aucune commission n'est prélevée."""
    pct = commission_percent(organizer)
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
    commission, net = compute_amounts(total, event.organizer)
    return Order.objects.create(
        reference=make_reference("CMD"), buyer=buyer, event=event, ticket_type=ticket_type,
        quantity=quantity, unit_price=ticket_type.price, total=total,
        commission=commission, organizer_amount=net,
    )


def finalize_order(order, method_key, method_label, phone, provider_ref):
    """Marque la commande payée et crée ses billets. IDEMPOTENT : appelable plusieurs fois sans doublon.

    Utilisé par le paiement simulé (cartes…) ET par le webhook Mobile Money (payments.services.fulfil).
    Renvoie (order, newly_paid). Si le stock est épuisé entre-temps alors que l'argent est déjà
    encaissé, la commande passe en « À rembourser » (aucun billet créé) pour traitement manuel.
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status != Order.Status.PENDING:
            return order, False
        tt = TicketType.objects.select_for_update().get(pk=order.ticket_type_id)
        order.paid_at = timezone.now()
        order.payment_method, order.payment_label = method_key, method_label
        order.payment_phone, order.payment_ref = phone, provider_ref
        if tt.remaining < order.quantity:
            order.status = Order.Status.NEEDS_REFUND
            order.save()
            logger.error("Commande %s payée mais stock épuisé : remboursement nécessaire", order.reference)
            return order, False
        order.status = Order.Status.PAID
        # La commission suit l'abonnement de l'organisateur AU MOMENT DU PAIEMENT (abonné : 0 %, sinon 2,5 %).
        order.commission, order.organizer_amount = compute_amounts(order.total, order.event.organizer)
        order.save()
        for _ in range(order.quantity):
            Ticket.objects.create(order=order, reference=make_reference("TK", 10))
    return order, True


def start_fedapay_order(request, order):
    """Paiement d'une commande via la page FedaPay (Mobile Money, carte…). Renvoie la Transaction (à ouvrir via fedapay.next_url).

    Mêmes garde-fous que le Mobile Money direct ; une transaction FedaPay encore en attente depuis moins de 30 min est reprise.
    """
    from datetime import timedelta

    from payments import fedapay
    from payments.models import Transaction

    if order.status != Order.Status.PENDING:
        raise PurchaseError("Cette commande n'est plus en attente de paiement.")
    if order.buyer_id == order.event.organizer_id:
        raise PurchaseError("Vous ne pouvez pas acheter de billets pour votre propre événement.")
    if order.event.sales_closed:
        raise PurchaseError("La vente des billets est terminée.")
    if order.ticket_type.remaining < order.quantity:
        raise PurchaseError("Stock épuisé entre-temps : il ne reste plus assez de billets.")
    recent = order.transactions.filter(provider=Transaction.Provider.FEDAPAY, status=Transaction.Status.PENDING,
                                       created_at__gte=timezone.now() - timedelta(minutes=30)).exclude(checkout_url="").first()
    if recent:
        return recent
    return fedapay.start_checkout(request, user=order.buyer, amount=order.total, description=f"Billets {order.event.name}", order=order)


def start_mobile_money(order, method, phone, callback_url):
    """Démarre (ou reprend) un paiement MTN MoMo / Moov Money pour une commande. Renvoie la Transaction.

    - le montant est celui de la commande (jamais celui du navigateur) ;
    - une transaction déjà en attente depuis moins de 5 min est reprise : pas de double demande
      sur le téléphone du client si la page est rechargée.
    """
    from datetime import timedelta

    from payments.models import Transaction
    from payments.services import PaymentError, create_transaction, launch_push

    if order.status != Order.Status.PENDING:
        raise PurchaseError("Cette commande n'est plus en attente de paiement.")
    if order.buyer_id == order.event.organizer_id:
        raise PurchaseError("Vous ne pouvez pas acheter de billets pour votre propre événement.")
    if order.event.sales_closed:
        raise PurchaseError("La vente des billets est terminée.")
    if order.ticket_type.remaining < order.quantity:
        raise PurchaseError("Stock épuisé entre-temps : il ne reste plus assez de billets.")

    recent = order.transactions.filter(
        status=Transaction.Status.PENDING, created_at__gte=timezone.now() - timedelta(minutes=5)).first()
    if recent:
        return recent
    try:
        tx = create_transaction(user_email=order.buyer.email, phone_number=phone, amount=order.total,
                                provider=method["provider"], order=order, country=order.buyer.country)
    except PaymentError as exc:
        raise PurchaseError(str(exc))
    launch_push(tx, callback_url)
    return tx


def schedule_receipt(order):
    """Envoie le reçu e-mail une fois la transaction SQL validée (jamais sur un rollback)."""
    transaction.on_commit(lambda: send_receipt(order))


def pay_order(order, method_key, phone, send_email=True):
    """Paiement SIMULÉ d'une commande (cartes, wallets non encore branchés). Renvoie (order, ok, message).

    Le Mobile Money MTN / Moov passe par payments (push + webhook), pas par cette fonction.
    """
    method = find_method(order.buyer.country, method_key)
    if method is None:
        raise PurchaseError("Moyen de paiement indisponible dans votre pays.")
    if method["kind"] == "momo" and len("".join(c for c in phone if c.isdigit())) < 8:
        raise PurchaseError("Saisissez le numéro Mobile Money à débiter.")
    if order.buyer_id == order.event.organizer_id:
        raise PurchaseError("Vous ne pouvez pas acheter de billets pour votre propre événement.")
    if order.event.sales_closed:
        raise PurchaseError("La vente des billets est terminée.")
    if order.ticket_type.remaining < order.quantity and order.status == Order.Status.PENDING:
        raise PurchaseError("Stock épuisé entre-temps : il ne reste plus assez de billets.")
    if order.status == Order.Status.PAID:
        return order, True, "Commande déjà payée."

    ok, provider_ref, message = process_payment(method, phone, order.total)
    if not ok:
        return order, False, message
    order, newly_paid = finalize_order(order, method["key"], method["label"], phone, provider_ref)
    if newly_paid and send_email:
        send_receipt(order)
    return order, True, message


# ----------------------------------------------------------------------------- retraits

def organizer_balance(user):
    earned = Order.objects.filter(event__organizer=user, status=Order.Status.PAID).aggregate(s=Sum("organizer_amount"))["s"] or 0
    withdrawn = Withdrawal.objects.filter(organizer=user).aggregate(s=Sum("amount"))["s"] or 0
    return earned - withdrawn


@transaction.atomic
def request_withdrawal(user, amount, payout_method):
    """Retrait vers un moyen enregistré par l'organisateur (payouts.PayoutMethod).

    Le verrou sur la ligne utilisateur sérialise les retraits d'un même organisateur : deux demandes
    simultanées ne peuvent pas dépasser le solde. Le virement réel (API de l'opérateur) se branche ici.
    """
    from django.contrib.auth import get_user_model
    get_user_model().objects.select_for_update().get(pk=user.pk)

    if payout_method is None or payout_method.organizer_id != user.id:
        raise PurchaseError("Choisissez l'un de vos moyens de retrait.")
    if amount < settings.MIN_WITHDRAWAL:
        raise PurchaseError(f"Le retrait minimum est de {settings.MIN_WITHDRAWAL} {settings.CURRENCY}.")
    if amount > organizer_balance(user):
        raise PurchaseError("Montant supérieur à votre solde disponible.")
    return Withdrawal.objects.create(
        organizer=user, payout_method=payout_method, amount=amount, method=payout_method.kind,
        method_label=payout_method.kind_label, phone=payout_method.display_account,   # instantané masqué
    )


# ----------------------------------------------------------------------------- QR code

def ticket_signature(reference):
    """Signature courte (HMAC dérivé de SECRET_KEY) de la référence : le QR porte « ?s=… ».

    Elle empêche d'énumérer des références au hasard sur la page publique de vérification, et de fabriquer un lien
    de vérification valide sans avoir vu le vrai QR code. (Un QR photographié reste copiable : le premier scan gagne,
    les suivants sont signalés « déjà utilisé » — voir scanner.services.check_in.)"""
    from django.utils.crypto import salted_hmac
    return salted_hmac("novatickets.ticket-qr.v1", reference).hexdigest()[:16]


def verify_url(ticket):
    return settings.SITE_URL.rstrip("/") + reverse("core:verify", args=[ticket.reference]) + "?s=" + ticket_signature(ticket.reference)


def qr_png(data, color=GREEN):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=color),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ----------------------------------------------------------------------------- PDF

TICKET_PAGE = (210, 90)  # mm


def _draw_ticket(c, ticket):
    """Dessine un billet « boarding pass » sur la page courante du canvas reportlab (format paysage)."""
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase.pdfmetrics import stringWidth

    order, event, user = ticket.order, ticket.order.event, ticket.order.buyer
    W, H = TICKET_PAGE[0] * mm, TICKET_PAGE[1] * mm
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


def tickets_pdf(tickets, title="Billets NovaTickets"):
    """PDF contenant un billet par page (un seul fichier pour toute une commande)."""
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(TICKET_PAGE[0] * mm, TICKET_PAGE[1] * mm))
    c.setTitle(title)
    c.setAuthor(settings.PLATFORM_NAME)
    for ticket in tickets:
        _draw_ticket(c, ticket)
        c.showPage()
    c.save()
    return buf.getvalue()


def ticket_pdf(ticket):
    """Billet officiel au format PDF."""
    return tickets_pdf([ticket], title=f"Billet {ticket.reference}")


# ----------------------------------------------------------------------------- reçu PDF

def mask_phone(phone):
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    return (digits[:3] + "•" * max(len(digits) - 5, 0) + digits[-2:]) if len(digits) > 5 else phone or "—"


def receipt_data(order):
    """Données du reçu d'une commande : un seul dictionnaire pour le PDF ET l'e-mail (donc toujours identiques)."""
    ev, buyer = order.event, order.buyer
    logo = ev.logo_or_none
    first = order.tickets.first()
    return {
        "reference": order.reference, "date": order.paid_at or order.created_at, "thanks": "Merci pour votre achat !",
        "event": {"name": ev.name, "when": f"{ev.start_date:%d/%m/%Y} à {ev.start_time:%H:%M}", "where": ev.location,
                  "logo": _logo_bytes(logo.path) if logo else None},
        "spectator": [("Nom", buyer.last_name.upper() or "—"), ("Prénom", buyer.first_name or "—"),
                      ("Email", buyer.email), ("Téléphone", buyer.phone or "—")],
        "details_title": "Détails du ticket",
        "details": [("Type de ticket payé", order.ticket_type.name), ("Référence", order.reference),
                    ("Prix unitaire", f"{int(order.unit_price):,}".replace(",", " ") + f" {settings.CURRENCY}"),
                    ("Quantité", order.quantity), ("Moyen de paiement", order.payment_label or "—")],
        "status": "Payé", "total": order.total,
        "signature": ev.organizer.signature_text, "signature_image": ev.organizer.signature_png, "organizer": ev.organizer.organizer_label,
        "qr": qr_png(verify_url(first)) if first else None,
    }


def order_receipt_pdf(order):
    """Reçu de paiement PDF d'une commande payée (format de la maquette)."""
    from core.pdf import render_receipt

    return render_receipt(receipt_data(order))


def _logo_bytes(path, size=220):
    """Logo réduit en PNG (léger pour l'e-mail, lisible par tous les clients). None si illisible."""
    from PIL import Image

    try:
        with Image.open(path) as im:
            im = im.convert("RGBA")
            im.thumbnail((size, size))
            out = io.BytesIO()
            im.save(out, "PNG", optimize=True)
            return out.getvalue()
    except Exception:
        return None


# ----------------------------------------------------------------------------- e-mail reçu

class ReceiptEmail(EmailMultiAlternatives):
    """E-mail HTML avec images intégrées (multipart/related) + PDF en pièces jointes.

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


def build_receipt_email(data, *, to, subject, attachments=()):
    """Construit l'e-mail de reçu (HTML de la maquette + version texte) à partir des données du reçu."""
    from core.pdf import long_date, social_links, static_path

    ctx = {**data, "platform": settings.PLATFORM_NAME, "currency": settings.CURRENCY, "date_label": long_date(data["date"]),
           "total_label": f"{int(data['total']):,}".replace(",", " ") + f" {settings.CURRENCY}",
           "socials": social_links(), "has_event_logo": bool(data.get("event") and data["event"].get("logo")),
           "has_qr": bool(data.get("qr"))}
    images = [("logo", static_path("img/logo-horizontal.png").read_bytes()), ("mark", static_path("img/logo.png").read_bytes())]
    for key, _ in ctx["socials"]:
        images.append((f"social_{key}", static_path(f"img/social/{key}.png").read_bytes()))
    if ctx["has_event_logo"]:
        images.append(("eventlogo", data["event"]["logo"]))
    if ctx["has_qr"]:
        images.append(("qr", data["qr"]))
    ctx["has_sign_image"] = bool(data.get("signature_image"))
    if ctx["has_sign_image"]:
        images.append(("signature", data["signature_image"]))
    msg = ReceiptEmail(subject=subject, body=render_to_string("emails/receipt.txt", ctx),
                       from_email=settings.DEFAULT_FROM_EMAIL, to=[to])
    msg.attach_alternative(render_to_string("emails/receipt.html", ctx), "text/html")
    msg.inline_images = images
    for name, content in attachments:
        msg.attach(name, content, "application/pdf")
    return msg


def send_receipt(order):
    """Reçu e-mail automatique après un paiement validé : reçu PDF + un billet PDF par place en pièces jointes."""
    attachments = [(f"recu-{order.reference}.pdf", order_receipt_pdf(order))]
    attachments += [(f"billet-{t.reference}.pdf", ticket_pdf(t)) for t in order.tickets.all()]
    msg = build_receipt_email(receipt_data(order), to=order.buyer.email, attachments=attachments,
                              subject=f"Votre reçu {settings.PLATFORM_NAME} — {order.event.name}")
    msg.send(fail_silently=True)
