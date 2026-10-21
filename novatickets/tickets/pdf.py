"""Ticket PDF au style « boarding pass » (ReportLab).

Une page par ticket : bandeau vert, logos plateforme + organisateur, passager, photo,
type de ticket, événement, talon détachable avec QR code stylisé.
"""
import io
from functools import lru_cache

from django.conf import settings
from django.utils.formats import date_format
from PIL import Image, ImageDraw, ImageOps
from reportlab.lib.colors import HexColor, white
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .qr import qr_image, ticket_url

FONTS = settings.BASE_DIR / "static" / "fonts"
PAGE_W, PAGE_H = 230 * mm, 96 * mm
GREEN, GREEN_DARK, GREEN_SOFT = HexColor("#16a34a"), HexColor("#14532d"), HexColor("#f0fdf4")
INK, MUTED, LINE = HexColor("#0f172a"), HexColor("#64748b"), HexColor("#bbf7d0")
STUB_X = 165 * mm


@lru_cache(maxsize=1)
def register_fonts():
    for name, file in (("Poppins", "Poppins-Regular"), ("Poppins-Medium", "Poppins-Medium"),
                       ("Poppins-Bold", "Poppins-Bold"), ("Poppins-Light", "Poppins-Light")):
        pdfmetrics.registerFont(TTFont(name, str(FONTS / f"{file}.ttf")))
    return True


def fit_text(text: str, font: str, size: float, max_w: float) -> str:
    """Tronque avec « … » pour tenir dans `max_w` points."""
    text = text or ""
    if pdfmetrics.stringWidth(text, font, size) <= max_w:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def contain(path_or_file, w_px: int, h_px: int) -> Image.Image | None:
    """Image redimensionnée pour tenir dans la boîte (fond transparent conservé)."""
    try:
        img = Image.open(path_or_file).convert("RGBA")
    except Exception:
        return None
    img.thumbnail((w_px, h_px), Image.LANCZOS)
    return img


def rounded_cover(path_or_file, w_px: int, h_px: int, radius: int) -> Image.Image | None:
    """Photo recadrée (cover) avec coins arrondis."""
    try:
        img = ImageOps.fit(Image.open(path_or_file).convert("RGB"), (w_px, h_px), Image.LANCZOS)
    except Exception:
        return None
    mask = Image.new("L", (w_px, h_px), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w_px - 1, h_px - 1], radius=radius, fill=255)
    out = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def placeholder_avatar(w_px: int, h_px: int, radius: int) -> Image.Image:
    img = Image.new("RGBA", (w_px, h_px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w_px - 1, h_px - 1], radius=radius, fill=(220, 252, 231, 255))
    cx = w_px // 2
    d.ellipse([cx - w_px * .17, h_px * .22, cx + w_px * .17, h_px * .22 + w_px * .34], fill=(134, 239, 172, 255))
    d.ellipse([cx - w_px * .32, h_px * .62, cx + w_px * .32, h_px * 1.3], fill=(134, 239, 172, 255))
    mask = Image.new("L", (w_px, h_px), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w_px - 1, h_px - 1], radius=radius, fill=255)
    img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", (w_px, h_px), 0), mask))
    return img


def _img(c, img: Image.Image, x, y, w, h):
    c.drawImage(ImageReader(img), x, y, width=w, height=h, mask="auto")


def _label_value(c, x, y, label, value, w, big=False):
    c.setFillColor(MUTED)
    c.setFont("Poppins-Medium", 6.5)
    c.drawString(x, y, label.upper())
    c.setFillColor(INK)
    font, size = ("Poppins-Bold", 12.5) if big else ("Poppins-Medium", 9.5)
    c.setFont(font, size)
    c.drawString(x, y - 5.2 * mm, fit_text(value, font, size, w))


def _draw_frame(c):
    c.setFillColor(white)
    c.setStrokeColor(LINE)
    c.setLineWidth(1)
    c.roundRect(4 * mm, 4 * mm, PAGE_W - 8 * mm, PAGE_H - 8 * mm, 5 * mm, fill=1, stroke=1)
    # Bandeau vert (haut) clippé aux coins arrondis
    c.saveState()
    p = c.beginPath()
    p.roundRect(4 * mm, 4 * mm, PAGE_W - 8 * mm, PAGE_H - 8 * mm, 5 * mm)
    c.clipPath(p, stroke=0, fill=0)
    c.setFillColor(GREEN_DARK)
    c.rect(0, PAGE_H - 24 * mm, PAGE_W, 20 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN_SOFT)
    c.rect(STUB_X, 0, PAGE_W - STUB_X, PAGE_H - 24 * mm, fill=1, stroke=0)
    c.setFillColor(GREEN)
    c.rect(0, 4 * mm, PAGE_W, 9 * mm, fill=1, stroke=0)
    c.restoreState()
    # Perforation + encoches
    c.setStrokeColor(HexColor("#86efac"))
    c.setDash(2, 3)
    c.line(STUB_X, 13 * mm, STUB_X, PAGE_H - 24 * mm)
    c.setDash()
    c.setFillColor(HexColor("#ffffff"))
    c.setStrokeColor(LINE)
    for y in (PAGE_H - 24 * mm, 13 * mm):
        c.circle(STUB_X, y, 3.2 * mm, fill=1, stroke=1)


def _draw_header(c, ticket):
    event, org = ticket.event, ticket.event.organizer
    logo = contain(settings.BASE_DIR / "static" / "img" / "logo.png", 640, 180)
    if logo:
        plate_w, plate_h = 52 * mm, 14.5 * mm
        c.setFillColor(white)
        c.roundRect(10 * mm, PAGE_H - 22 * mm, plate_w, 16 * mm, 3 * mm, fill=1, stroke=0)
        ratio = min((plate_w - 4 * mm) / logo.width, (plate_h - 2 * mm) / logo.height)
        w, h = logo.width * ratio, logo.height * ratio
        _img(c, logo, 10 * mm + (plate_w - w) / 2, PAGE_H - 22 * mm + (16 * mm - h) / 2, w, h)
    c.setFillColor(white)
    c.setFont("Poppins-Medium", 7)
    c.drawRightString(STUB_X - 28 * mm, PAGE_H - 11.5 * mm, "ORGANISÉ PAR")
    c.setFont("Poppins-Bold", 10)
    c.drawRightString(STUB_X - 28 * mm, PAGE_H - 16.5 * mm,
                      fit_text(org.display_org, "Poppins-Bold", 10, 62 * mm))
    org_logo_file = event.logo or org.organisation_logo
    c.setFillColor(white)
    c.roundRect(STUB_X - 24 * mm, PAGE_H - 22 * mm, 16 * mm, 16 * mm, 3 * mm, fill=1, stroke=0)
    img = contain(org_logo_file, 300, 300) if org_logo_file else None
    if img:
        r = min(13 * mm / img.width, 13 * mm / img.height)
        w, h = img.width * r, img.height * r
        _img(c, img, STUB_X - 24 * mm + (16 * mm - w) / 2, PAGE_H - 22 * mm + (16 * mm - h) / 2, w, h)
    c.setFillColor(GREEN_DARK)
    c.setFont("Poppins-Bold", 8)
    c.drawRightString(PAGE_W - 12 * mm, PAGE_H - 12 * mm, "BOARDING PASS")
    c.setFillColor(HexColor("#86efac"))
    c.setFont("Poppins-Medium", 7)
    c.setFillColor(white)
    c.drawRightString(PAGE_W - 12 * mm, PAGE_H - 17 * mm, "TICKET D'ENTRÉE")


def _draw_body(c, ticket):
    event = ticket.event
    left, right_limit = 11 * mm, STUB_X - 38 * mm
    c.setFillColor(GREEN)
    c.setFont("Poppins-Bold", 7)
    c.drawString(left, PAGE_H - 32 * mm, "ÉVÉNEMENT")
    c.setFillColor(INK)
    c.setFont("Poppins-Bold", 17)
    c.drawString(left, PAGE_H - 39.5 * mm, fit_text(event.name, "Poppins-Bold", 17, right_limit - left))
    when = f"{date_format(event.start_date, 'l j F Y')} · {event.start_time:%H:%M}".capitalize()
    c.setFillColor(MUTED)
    c.setFont("Poppins", 8.5)
    c.drawString(left, PAGE_H - 45 * mm, fit_text(when, "Poppins", 8.5, right_limit - left))

    y1, y2 = PAGE_H - 56 * mm, PAGE_H - 70 * mm
    _label_value(c, left, y1, "Passager", ticket.holder_name, 62 * mm, big=True)
    _label_value(c, left + 66 * mm, y1, "Sexe", ticket.holder_sexe_label, 24 * mm)
    _label_value(c, left, y2, "Type de ticket", ticket.ticket_type.name, 62 * mm)
    place = ", ".join(x for x in (event.venue, event.city) if x) or "—"
    _label_value(c, left + 66 * mm, y2, "Lieu", place, right_limit - left - 66 * mm)

    # Photo du passager
    pw, ph = 28 * mm, 34 * mm
    px, py = STUB_X - 38 * mm + 4 * mm, PAGE_H - 70 * mm - 1 * mm
    photo = ticket.photo_file
    img = rounded_cover(photo, 280, 340, 28) if photo else None
    _img(c, img or placeholder_avatar(280, 340, 28), px, py, pw, ph)
    c.setStrokeColor(LINE)
    c.setLineWidth(1.2)
    c.roundRect(px, py, pw, ph, 2.8 * mm, fill=0, stroke=1)

    c.setFillColor(white)
    c.setFont("Poppins-Medium", 7.5)
    c.drawString(left, 7.4 * mm, "Présentez ce ticket (QR code) à l'entrée · Un ticket = une personne")
    c.drawRightString(STUB_X - 6 * mm, 7.4 * mm, f"Réf. {ticket.reference}")


def _draw_stub(c, ticket, index, total):
    qr = qr_image(ticket_url(ticket), box_size=8)
    size = 42 * mm
    x = STUB_X + (PAGE_W - STUB_X - size) / 2
    _img(c, qr.convert("RGBA"), x, PAGE_H - 28 * mm - size - 2 * mm, size, size)
    c.setFillColor(GREEN_DARK)
    c.setFont("Poppins-Bold", 9)
    c.drawCentredString((STUB_X + PAGE_W) / 2, 22 * mm, ticket.reference)
    c.setFillColor(MUTED)
    c.setFont("Poppins", 7)
    c.drawCentredString((STUB_X + PAGE_W) / 2, 17.8 * mm, f"Ticket {index} / {total} · {ticket.ticket_type.name}"[:38])
    c.setFillColor(white)
    c.setFont("Poppins-Bold", 7.5)
    c.drawCentredString((STUB_X + PAGE_W) / 2, 7.4 * mm, "novatickets")


def tickets_pdf(tickets) -> bytes:
    """PDF (une page par ticket) pour une liste de tickets d'une même commande ou non."""
    register_fonts()
    tickets = list(tickets)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"Ticket NovaTickets — {tickets[0].event.name}" if tickets else "Tickets NovaTickets")
    c.setAuthor("NovaTickets")
    for t in tickets:
        siblings = t.order.tickets.count()
        index = list(t.order.tickets.values_list("pk", flat=True)).index(t.pk) + 1
        _draw_frame(c)
        _draw_header(c, t)
        _draw_body(c, t)
        _draw_stub(c, t, index, siblings)
        c.showPage()
    c.save()
    return buf.getvalue()
