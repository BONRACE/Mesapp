"""Reçu de paiement PDF (reportlab), fidèle à la maquette NovaTickets :

logo + « Plateforme de Billetterie » + date, logos plateforme / événement, « Merci pour votre achat ! »,
informations du spectateur, détails du ticket, signature de l'organisateur, pied de page (Powered by, réseaux, QR).
Un seul gabarit, alimenté par un dictionnaire : il sert aux reçus de commande et aux reçus de transaction.
"""
import io
from pathlib import Path

from django.conf import settings
from django.utils import timezone

NAVY, ORANGE, INK, GREY, LINE, SOFT = "#12497f", "#f28c28", "#111827", "#64748b", "#cbd5e1", "#f1f5f9"
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def money(n):
    """15000 -> '15 000 FCFA' (espace simple : les polices de base du PDF n'ont pas l'espace insécable fine)."""
    return f"{int(n):,}".replace(",", " ") + f" {settings.CURRENCY}"


def long_date(dt):
    dt = timezone.localtime(dt) if timezone.is_aware(dt) else dt
    return f"{dt.day} {MONTHS[dt.month - 1]} {dt.year}"


def static_path(name):
    return Path(settings.BASE_DIR, "static", name)


def social_links():
    """URL des réseaux sociaux : réglage SOCIAL_LINKS, à défaut le site (jamais de lien inventé)."""
    links = getattr(settings, "SOCIAL_LINKS", {})
    return [(key, links.get(key) or settings.SITE_URL) for key in ("x", "facebook", "instagram")]


def render_receipt(data):
    """Reçu A4.

    data = {
      "reference": "CMD-XXXX", "date": datetime, "thanks": "Merci pour votre achat !",
      "event": {"name": "…", "when": "28/10/2026 à 19:30", "where": "…", "logo": bytes | None} | None,
      "spectator": [("Nom", "…"), ("Prénom", "…"), ("E-mail", "…"), ("Téléphone", "…")],
      "details": [("Type de ticket payé", "…"), ("Référence", "…"), …],     # boîte « Détails du ticket »
      "details_title": "Détails du ticket", "status": "Payé", "total": 15000,
      "signature": "Adama Touré – Directeur" | None, "organizer": "Africa Rhythm Fest" | None,
      "qr": bytes | None,
    }
    """
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    W, H = A4
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Reçu {data['reference']}")
    c.setAuthor(settings.PLATFORM_NAME)
    navy, orange, ink, grey, line, soft = (HexColor(x) for x in (NAVY, ORANGE, INK, GREY, LINE, SOFT))
    left, right, mid = 20 * mm, W - 20 * mm, W / 2

    def image(src, x, y, w, h):
        try:
            c.drawImage(ImageReader(io.BytesIO(src) if isinstance(src, bytes) else str(src)), x, y, w, h,
                        mask="auto", preserveAspectRatio=True, anchor="c")
            return True
        except Exception:
            return False

    # --- en-tête : logo, « Plateforme de Billetterie », date
    image(static_path("img/logo-horizontal.png"), mid - 33 * mm, H - 33 * mm, 66 * mm, 21 * mm)
    c.setFillColor(grey)
    c.setFont("Helvetica", 10)
    c.drawCentredString(mid, H - 38 * mm, "Plateforme de Billetterie")
    c.setFont("Helvetica", 9)
    c.drawCentredString(mid, H - 43.5 * mm, f"Date : {long_date(data['date'])}  ·  Réf. {data['reference']}")
    c.setStrokeColor(line)
    c.setLineWidth(0.7)
    c.line(left, H - 48 * mm, right, H - 48 * mm)
    y = H - 52 * mm

    # --- logos plateforme + événement
    ev = data.get("event")
    if ev and ev.get("logo"):
        image(static_path("img/logo.png"), mid - 25 * mm, y - 18 * mm, 18 * mm, 18 * mm)
        c.setFillColor(orange)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(mid, y - 11 * mm, "+")
        image(ev["logo"], mid + 7 * mm, y - 18 * mm, 18 * mm, 18 * mm)
        y -= 25 * mm
    else:
        y -= 4 * mm

    # --- remerciement + événement
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(left, y, data.get("thanks", "Merci pour votre achat !"))
    y -= 9 * mm
    if ev:
        c.setFillColor(grey)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(left, y, "Nom de l'événement")
        y -= 6 * mm
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(left, y, ev["name"][:70])
        y -= 5.5 * mm
        c.setFillColor(grey)
        c.setFont("Helvetica", 9)
        c.drawString(left, y, f"{ev['when']}  ·  {ev['where']}"[:110])
        y -= 9 * mm
    else:
        y -= 2 * mm

    def heading(text):
        nonlocal y
        c.setFillColor(navy)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(left, y, text)
        c.setStrokeColor(orange)
        c.setLineWidth(1.6)
        c.line(left, y - 2 * mm, left + 10 * mm, y - 2 * mm)
        y -= 8 * mm

    def rows(pairs, x0, x1, size=10):
        nonlocal y
        for label, value in pairs:
            c.setFillColor(grey)
            c.setFont("Helvetica", size)
            c.drawString(x0, y, f"{label} :")
            c.setFillColor(ink)
            c.setFont("Helvetica-Bold", size)
            c.drawRightString(x1, y, str(value)[:60])
            y -= 6.2 * mm

    # --- informations du spectateur
    if data.get("spectator"):
        heading("Informations du spectateur")
        rows(data["spectator"], left, right)
        y -= 4 * mm

    # --- détails du ticket (boîte grise)
    heading(data.get("details_title", "Détails du ticket"))
    details = data["details"] + [("Statut du paiement", data.get("status", "Payé"))]
    box_h = len(details) * 6.2 * mm + 18 * mm
    c.setFillColor(soft)
    c.setStrokeColor(line)
    c.setLineWidth(0.8)
    c.roundRect(left, y - box_h + 5 * mm, right - left, box_h, 3 * mm, fill=1, stroke=1)
    y -= 2 * mm
    rows(details, left + 5 * mm, right - 5 * mm)
    c.setStrokeColor(line)
    c.line(left + 5 * mm, y + 3.5 * mm, right - 5 * mm, y + 3.5 * mm)
    y -= 2.5 * mm
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(left + 5 * mm, y, "Montant total :")
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(right - 5 * mm, y - 0.5 * mm, money(data["total"]))
    y -= 14 * mm

    # --- signature de l'organisateur
    if data.get("signature"):
        c.setFillColor(ink)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left, y, "Signature de l'organisateur :")
        y -= 3 * mm
        c.setStrokeColor(line)
        c.roundRect(left, y - 19 * mm, right - left, 19 * mm, 3 * mm, fill=0, stroke=1)
        c.setFillColor(navy)
        c.setFont("Times-BoldItalic", 17)
        c.drawString(left + 6 * mm, y - 9.5 * mm, data["signature"][:48])
        c.saveState()                                     # tampon « vérifié par »
        c.translate(right - 22 * mm, y - 9.5 * mm)
        c.rotate(4)
        c.setStrokeColor(orange)
        c.setLineWidth(1.3)
        c.roundRect(-18 * mm, -6 * mm, 36 * mm, 12 * mm, 2 * mm, fill=0, stroke=1)
        c.setFillColor(orange)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(0, 1.2 * mm, "VÉRIFIÉ PAR")
        c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(0, -3.4 * mm, settings.PLATFORM_NAME.upper())
        c.restoreState()
        if data.get("organizer"):
            c.setFillColor(grey)
            c.setFont("Helvetica", 8)
            c.drawString(left + 6 * mm, y - 15.5 * mm, data["organizer"][:70])
        y -= 25 * mm

    # --- pied de page
    c.setStrokeColor(line)
    c.setLineWidth(0.7)
    c.line(left, 36 * mm, right, 36 * mm)
    c.setFillColor(grey)
    c.setFont("Helvetica", 9)
    c.drawString(left, 28 * mm, "Powered by")
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(left + 19.5 * mm, 28 * mm, settings.PLATFORM_NAME)
    c.setFillColor(grey)
    c.setFont("Helvetica", 7.5)
    c.drawString(left, 22.5 * mm, "La billetterie en ligne pour l'Afrique de l'Ouest.")
    c.drawString(left, 18.5 * mm, "Document généré automatiquement par la plateforme.")
    x = right - 62 * mm if data.get("qr") else right - 24 * mm
    for key, url in social_links():
        if image(static_path(f"img/social/{key}.png"), x, 26 * mm, 7 * mm, 7 * mm):
            c.linkURL(url, (x, 26 * mm, x + 7 * mm, 33 * mm), relative=0)
        x += 9.5 * mm
    if data.get("qr"):
        image(data["qr"], right - 24 * mm, 14 * mm, 24 * mm, 24 * mm)
    c.showPage()
    c.save()
    return buf.getvalue()
