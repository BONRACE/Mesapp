"""Génération du QR code et du billet PDF — style 'ticket d'événement officiel'."""
import io
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import SquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Palette — carte claire "ticket officiel"
COLOR_NAVY = HexColor("#166534")
COLOR_NAVY_SOFT = HexColor("#F0FDF4")
COLOR_BORDER = HexColor("#CDEEDA")
COLOR_GOLD = HexColor("#86EFAC")
COLOR_GREEN = HexColor("#22C55E")
COLOR_RED = HexColor("#EF4444")
COLOR_GRAY = HexColor("#5B6B82")
COLOR_MUTED = HexColor("#8494A8")
COLOR_DARK = HexColor("#0B2818")
COLOR_PHOTO_BG = HexColor("#E1F5E7")
COLOR_DECOR = HexColor("#D7F0DF")


def generate_qr_bytes(payload: str) -> bytes:
    """QR classique noir sur blanc, net et scannable, conforme au modèle officiel."""
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=SquareModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=(11, 40, 24)),
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _statut_label(ticket):
    return {
        "valide": ("PAYÉ ET VALIDÉ", COLOR_GREEN, "\u2714"),
        "utilise": ("DÉJÀ UTILISÉ", COLOR_MUTED, "\u21ba"),
        "annule": ("ANNULÉ", COLOR_RED, "\u2715"),
    }.get(ticket.statut, ("PAYÉ ET VALIDÉ", COLOR_GREEN, "\u2714"))


def build_ticket_pdf(ticket) -> bytes:
    """Génère le PDF du billet, au format 'ticket d'événement officiel' (carte claire)."""
    buf = io.BytesIO()
    width, height = 180 * mm, 153 * mm
    c = canvas.Canvas(buf, pagesize=(width, height))
    event = ticket.event
    spectateur = ticket.spectateur

    # Fond blanc
    c.setFillColor(white)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    y = height  # curseur vertical, on descend

    # --- 1. En-tête : logos plateforme / organisateur ---
    header_h = 20 * mm
    c.setFillColor(COLOR_NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(9 * mm, y - 9 * mm, "\u2726 PLATEFORME")
    c.drawString(9 * mm, y - 14 * mm, "DE BILLETTERIE")

    c.setStrokeColor(COLOR_BORDER)
    c.line(width / 2, y - 5 * mm, width / 2, y - 16 * mm)

    org_name = (event.organisateur.nom_structure or event.organisateur.nom_complet).upper()
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(COLOR_NAVY)
    c.drawRightString(width - 9 * mm, y - 9 * mm, "ORGANISATEUR")
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 9 * mm, y - 14 * mm, org_name[:28])
    y -= header_h

    # --- 2. Bandeau titre ---
    title_h = 13 * mm
    c.setFillColor(COLOR_NAVY)
    c.rect(0, y - title_h, width, title_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(9 * mm, y - title_h + 4.5 * mm, "TICKET D'ÉVÉNEMENT OFFICIEL")
    y -= title_h

    # --- 3. Corps : champs événement / photo / spectateur ---
    body_h = 43 * mm
    field_labels = [
        ("Événement", event.nom),
        ("Date", f"{event.date_debut.strftime('%d')}"
                 f"{'-' + event.date_fin.strftime('%d') if event.date_fin != event.date_debut else ''} "
                 f"{event.date_debut.strftime('%B %Y')}"),
        ("Heure", event.heure_debut.strftime("%Hh%M")),
        ("Lieu", f"{event.lieu}, {event.ville}" if event.lieu else (event.ville or "—")),
    ]
    fx, fy, fw, fh, gap = 9 * mm, y - 6 * mm, 92 * mm, 7.2 * mm, 1.3 * mm
    c.setFont("Helvetica", 8.5)
    for i, (label, value) in enumerate(field_labels):
        by = fy - i * (fh + gap)
        c.setFillColor(COLOR_NAVY_SOFT)
        c.roundRect(fx, by - fh, fw, fh, 2, fill=1, stroke=0)
        c.setStrokeColor(COLOR_BORDER)
        c.roundRect(fx, by - fh, fw, fh, 2, fill=0, stroke=1)
        c.setFillColor(COLOR_GRAY)
        c.setFont("Helvetica", 7.5)
        c.drawString(fx + 3 * mm, by - fh + 2.3 * mm, f"{label} :")
        c.setFillColor(COLOR_DARK)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(fx + 3 * mm + c.stringWidth(f"{label} : ", "Helvetica", 7.5), by - fh + 2.3 * mm, str(value)[:40])

    # Photo du spectateur
    photo_size = 20 * mm
    photo_x = fx + fw + 6 * mm
    photo_y = y - 8 * mm - photo_size
    c.setFillColor(COLOR_PHOTO_BG)
    c.roundRect(photo_x, photo_y, photo_size, photo_size, 2, fill=1, stroke=0)
    c.setStrokeColor(COLOR_BORDER)
    c.roundRect(photo_x, photo_y, photo_size, photo_size, 2, fill=0, stroke=1)
    if spectateur.photo:
        try:
            img = ImageReader(spectateur.photo.path)
            c.drawImage(img, photo_x, photo_y, photo_size, photo_size,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(photo_x + photo_size / 2, photo_y - 4 * mm, "Photo du Spectateur")

    # Infos spectateur (colonne droite)
    ix = photo_x + photo_size + 6 * mm
    iy = y - 8 * mm
    rows = [
        ("Nom", spectateur.nom or "—"),
        ("Prénom", spectateur.prenoms or "—"),
        ("Sexe", spectateur.get_sexe_display() or "—"),
        ("Profession", spectateur.profession or "—"),
    ]
    for i, (label, value) in enumerate(rows):
        ry = iy - i * 9 * mm
        c.setFillColor(COLOR_GRAY)
        c.setFont("Helvetica", 7.5)
        c.drawString(ix, ry, f"{label} :")
        c.setFillColor(COLOR_DARK)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawString(ix, ry - 4 * mm, str(value)[:26])
    y -= body_h

    # --- 4. Bandeau type de billet / statut ---
    type_h = 13 * mm
    c.setFillColor(COLOR_NAVY)
    c.rect(0, y - type_h, width, type_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8.5)
    label = f"TYPE DE TICKET : "
    c.drawString(9 * mm, y - type_h + 4.5 * mm, label)
    c.setFillColor(COLOR_GOLD)
    c.drawString(9 * mm + c.stringWidth(label, "Helvetica-Bold", 8.5), y - type_h + 4.5 * mm,
                 ticket.ticket_type.nom.upper())

    statut_text, statut_color, statut_icon = _statut_label(ticket)
    c.setFillColor(statut_color)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 9 * mm, y - type_h + 4.5 * mm, f"{statut_icon} STATUT : {statut_text}")
    y -= type_h

    # --- 5. QR code ---
    qr_h = 46 * mm
    qr_size = 26 * mm
    qr_cx = width / 2
    qr_top = y - 6 * mm

    c.setFillColor(COLOR_DECOR)
    c.setFont("Helvetica-Bold", 30)
    c.drawRightString(qr_cx - qr_size / 2 - 3 * mm, qr_top - qr_size / 2 - 4 * mm, "CO")
    c.drawString(qr_cx + qr_size / 2 + 3 * mm, qr_top - qr_size / 2 - 4 * mm, "QR")

    qr_bytes = generate_qr_bytes(ticket.qr_payload)
    qr_img = ImageReader(io.BytesIO(qr_bytes))
    c.setFillColor(white)
    c.roundRect(qr_cx - qr_size / 2 - 1.5 * mm, qr_top - qr_size - 1.5 * mm, qr_size + 3 * mm, qr_size + 3 * mm, 2, fill=1, stroke=0)
    c.drawImage(qr_img, qr_cx - qr_size / 2, qr_top - qr_size, qr_size, qr_size, mask='auto')

    c.setFillColor(COLOR_GRAY)
    c.setFont("Helvetica", 9)
    c.drawCentredString(qr_cx, qr_top - qr_size - 7 * mm, "Scanner pour l'entrée")
    c.setFillColor(COLOR_MUTED)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(qr_cx, qr_top - qr_size - 11.5 * mm, f"TICKET ID : #{ticket.code}")
    y -= qr_h

    # --- 6. Pied : conditions ---
    footer_h = y  # reste jusqu'en bas
    c.setFillColor(COLOR_NAVY)
    c.rect(0, 0, width, footer_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 6.5)
    c.drawCentredString(width / 2, footer_h - 5.5 * mm,
                         "Conditions : Ce billet est non-remboursable. Veuillez présenter")
    c.setFont("Helvetica", 6.5)
    c.drawCentredString(width / 2, footer_h - 9.5 * mm, "une pièce d'identité valide à l'entrée.")
    c.setFillColor(HexColor("#A7D8B7"))
    c.drawCentredString(width / 2, footer_h - 13.5 * mm, "Pour plus d'informations, visitez novatickets.bj")

    c.showPage()
    c.save()
    return buf.getvalue()
