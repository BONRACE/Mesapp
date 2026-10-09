"""Rendu des cartes de visite : PNG recto/verso (300 dpi), PDF et vCard."""
import io
from functools import lru_cache
from pathlib import Path

import qrcode
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

W, H = 1050, 600  # 3,5 x 2 pouces à 300 dpi (format carte standard)
FONT_DIR = Path(settings.BASE_DIR) / "static" / "fonts"
_FONTS = {"regular": "Inter-Regular.otf", "semibold": "Inter-SemiBold.otf", "bold": "Inter-Bold.otf"}
WHITE = (255, 255, 255)
INK = (15, 23, 42)
GREY = (100, 116, 139)


@lru_cache(maxsize=64)
def font(size, weight="regular"):
    return ImageFont.truetype(str(FONT_DIR / _FONTS[weight]), size)


def hex_rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def luminance(rgb):
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255


def text_w(draw, text, fnt):
    return draw.textlength(text, font=fnt)


def ellipsize(draw, text, fnt, max_w):
    if text_w(draw, text, fnt) <= max_w:
        return text
    while text and text_w(draw, text + "…", fnt) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if text_w(draw, trial, fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def load_logo(card):
    field = card.logo or getattr(card.user, "org_logo", None)
    if not field:
        return None
    try:
        with Image.open(field.path) as im:
            return im.convert("RGBA")
    except Exception:
        return None


# ------------------------------------------------------------------ vCard
def _esc(value):
    return (value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def website_url(card):
    site = card.website.strip()
    if site and not site.lower().startswith(("http://", "https://")):
        site = "https://" + site
    return site


def vcard_text(card):
    parts = card.contact_name.split()
    family = parts[-1] if parts else ""
    given = " ".join(parts[:-1])
    lines = [
        "BEGIN:VCARD", "VERSION:3.0",
        f"FN:{_esc(card.contact_name)}",
        f"N:{_esc(family)};{_esc(given)};;;",
        f"ORG:{_esc(card.company_name)}",
    ]
    if card.job_title:
        lines.append(f"TITLE:{_esc(card.job_title)}")
    if card.phone:
        lines.append(f"TEL;TYPE=CELL:{_esc(card.phone)}")
    if card.email:
        lines.append(f"EMAIL:{_esc(card.email)}")
    if card.website:
        lines.append(f"URL:{website_url(card)}")
    if card.address:
        lines.append(f"ADR;TYPE=WORK:;;{_esc(card.address)};;;;")
    if card.tagline:
        lines.append(f"NOTE:{_esc(card.tagline)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


# ------------------------------------------------------------------ recto
def render_recto(card):
    accent = hex_rgb(card.color)
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.ellipse((W - 330, -210, W + 170, 290), fill=mix(accent, WHITE, 0.88))
    d.ellipse((W - 210, -120, W + 60, 150), fill=mix(accent, WHITE, 0.76))
    d.rectangle((0, 0, 26, H), fill=accent)

    left, max_w = 84, W - 84 - 70
    top = 70
    logo = load_logo(card)
    if logo:
        logo.thumbnail((240, 140), Image.LANCZOS)
        img.paste(logo, (left, top + (140 - logo.height) // 2), logo)
    else:
        initials = "".join(w[0] for w in card.company_name.split()[:2]).upper() or "?"
        d.rounded_rectangle((left, top, left + 130, top + 130), radius=30, fill=accent)
        d.text((left + 65, top + 65), initials, font=font(56, "bold"), fill=WHITE, anchor="mm")

    # Nom de l'entreprise : on réduit la taille jusqu'à tenir sur 2 lignes
    y = 240
    for size in range(66, 36, -4):
        f = font(size, "bold")
        lines = wrap(d, card.company_name, f, max_w)
        if len(lines) <= 2 and all(text_w(d, ln, f) <= max_w for ln in lines):
            break
    for ln in [ellipsize(d, ln, f, max_w) for ln in lines[:2]]:
        d.text((left, y), ln, font=f, fill=INK)
        y += int(size * 1.18)
    if card.tagline:
        tf = font(30)
        d.text((left, y + 6), ellipsize(d, card.tagline, tf, max_w), font=tf, fill=GREY)

    d.line((left, 472, W - 70, 472), fill=(226, 232, 240), width=2)
    d.text((left, 488), ellipsize(d, card.contact_name, font(38, "semibold"), max_w), font=font(38, "semibold"), fill=INK)
    if card.job_title:
        d.text((left, 540), ellipsize(d, card.job_title, font(28), max_w), font=font(28), fill=accent)
    return img


# ------------------------------------------------------------------ verso
def _qr_image(text, inner):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=0)
    qr.add_data(text)
    qr.make(fit=True)
    n = qr.modules_count
    made = qr.make_image(fill_color="black", back_color="white")
    base = made.get_image() if hasattr(made, "get_image") else made._img
    box = max(1, inner // n)
    return base.convert("RGB").resize((n * box, n * box), Image.NEAREST)


def render_verso(card):
    bg = hex_rgb(card.color)
    fg = WHITE if luminance(bg) < 0.62 else INK
    soft = mix(fg, bg, 0.45)
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    d.ellipse((-170, H - 210, 270, H + 230), fill=mix(bg, fg, 0.08))

    left, tile = 70, 300
    tx = W - 70 - tile
    max_w = tx - left - 40

    # Nom : une ligne si possible, sinon deux lignes plus petites
    name_lines = [card.company_name]
    for size in range(46, 30, -2):
        nf = font(size, "bold")
        if text_w(d, card.company_name, nf) <= max_w:
            break
    else:
        size, nf = 34, font(34, "bold")
        name_lines = wrap(d, card.company_name, nf, max_w)[:2]
    ny = 66
    for ln in name_lines:
        d.text((left, ny), ellipsize(d, ln, nf, max_w), font=nf, fill=fg)
        ny += int(size * 1.2)
    rule_y = ny + 12
    d.rectangle((left, rule_y, left + 70, rule_y + 4), fill=soft)

    y = rule_y + 38
    rows = [("TÉLÉPHONE", card.phone), ("E-MAIL", card.email), ("SITE WEB", card.website), ("ADRESSE", card.address)]
    vf = font(30)
    for label, value in rows:
        if not value:
            continue
        d.text((left, y), label, font=font(20, "semibold"), fill=soft)
        lines = wrap(d, value, vf, max_w)[:2] if label == "ADRESSE" else [value]
        yy = y + 30
        for ln in lines:
            d.text((left, yy), ellipsize(d, ln, vf, max_w), font=vf, fill=fg)
            yy += 38
        y = yy + 16

    # QR code vCard : scanné avec le téléphone, il propose « Ajouter aux contacts »
    qimg = _qr_image(vcard_text(card), tile - 48)
    ty = (H - tile) // 2 - 26
    d.rounded_rectangle((tx, ty, tx + tile, ty + tile), radius=28, fill=WHITE)
    img.paste(qimg, (tx + (tile - qimg.width) // 2, ty + (tile - qimg.height) // 2))
    cap = font(22, "semibold")
    for i, line in enumerate(("Scannez pour ajouter", "le contact")):
        d.text((tx + tile // 2, ty + tile + 34 + i * 30), line, font=cap, fill=fg, anchor="mm")
    return img


# ------------------------------------------------------------------ sorties
def card_png(card, side):
    img = render_recto(card) if side == "recto" else render_verso(card)
    buf = io.BytesIO()
    img.save(buf, "PNG", dpi=(300, 300))
    return buf.getvalue()


def card_pdf(card):
    """PDF 2 pages (recto puis verso) au format carte 3,5 x 2 pouces, prêt pour l'imprimeur."""
    pw, ph = 252, 144
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(pw, ph))
    c.setTitle(f"Carte de visite – {card.company_name}")
    for side in ("recto", "verso"):
        c.drawImage(ImageReader(io.BytesIO(card_png(card, side))), 0, 0, width=pw, height=ph)
        c.showPage()
    c.save()
    return buf.getvalue()
