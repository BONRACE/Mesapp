"""Rendu des cartes de visite : recto/verso, 6 modèles, PNG 300 dpi et PDF (85 × 55 mm).

Le même moteur sert à l'aperçu en direct (filigrane « APERÇU », basse définition)
et à la génération finale (après paiement), pour que ce qu'on voit soit ce qu'on obtient.
"""
import io
import random
from dataclasses import dataclass
from functools import lru_cache
from types import SimpleNamespace

import numpy as np
import qrcode
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

W, H = 1004, 650  # 85 × 55 mm à 300 dpi
FONTS = settings.BASE_DIR / "static" / "fonts"


@lru_cache(maxsize=64)
def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"{name}.ttf"), size)


@dataclass(frozen=True)
class Theme:
    key: str
    bg: str            # fond du recto
    bg2: str           # fond du verso
    ink: str           # texte principal
    soft: str          # texte secondaire
    accent: str
    title: str = "Poppins-Bold"
    body: str = "Poppins-Medium"
    align: str = "left"
    x0: int = 80       # marge gauche du contenu
    x1: int = 70       # marge droite du contenu
    plate: bool = False   # logo posé sur une plaque blanche (fonds foncés)
    deboss: str = ""      # couleur du reflet « gravé » sous le texte


THEMES = {
    "emeraude": Theme("emeraude", "#ffffff", "#ffffff", "#0f2a1c", "#4b6358", "#16a34a", x0=100),
    "minuit": Theme("minuit", "#14284b", "#0f1f3b", "#ffffff", "#b6c2d9", "#f28c28", plate=True, x0=90),
    "kraft": Theme("kraft", "#c9a674", "#c9a674", "#3a281a", "#5e4630", "#7a4b22", title="Caladea-Bold",
                   body="Poppins-Medium", align="center", x0=90, x1=90, deboss="#e2c796"),
    "pagne": Theme("pagne", "#b5532a", "#fbf3e4", "#fff6e6", "#f3d9b8", "#e0a030", plate=True, x0=80, x1=230),
    "ivoire": Theme("ivoire", "#f8f2e2", "#f8f2e2", "#2a2a2a", "#6b6252", "#a8842f", title="Caladea-Bold",
                    body="Caladea-Regular", align="center", x0=100, x1=100),
    "sauge": Theme("sauge", "#eef5ef", "#f8fbf8", "#16281e", "#52685b", "#1f6f4a", x0=90),
}


# --- Petits utilitaires ---------------------------------------------------------

def _wrap(text, fnt, max_w):
    words, lines, cur = (text or "").split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if fnt.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_block(name, text, max_w, start, minimum, max_lines):
    """Plus grande taille (≤ start) pour que le texte tienne en `max_lines` lignes."""
    for size in range(start, minimum - 1, -2):
        fnt = font(name, size)
        lines = _wrap(text, fnt, max_w)
        if len(lines) <= max_lines and all(fnt.getlength(x) <= max_w for x in lines):
            return fnt, lines
    fnt = font(name, minimum)
    lines = _wrap(text, fnt, max_w)[:max_lines]
    if lines:
        while fnt.getlength(lines[-1] + "…") > max_w and len(lines[-1]) > 1:
            lines[-1] = lines[-1][:-1]
        if len(_wrap(text, fnt, max_w)) > max_lines:
            lines[-1] += "…"
    return fnt, lines


def _text(d, xy, text, fnt, fill, anchor="la", deboss=""):
    if deboss:
        d.text((xy[0] + 1, xy[1] + 2), text, font=fnt, fill=deboss, anchor=anchor)
    d.text(xy, text, font=fnt, fill=fill, anchor=anchor)


def _grain(img, strength=14, seed=7):
    """Grain de papier : bruit fin + quelques fibres."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    noise = rng.normal(0, strength, (img.height, img.width, 1)).astype(np.int16)
    out = Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(out, "RGBA")
    r = random.Random(seed)
    for _ in range(260):
        x, y, n = r.randint(0, img.width), r.randint(0, img.height), r.randint(8, 30)
        a = r.uniform(-.8, .8)
        d.line([(x, y), (x + n, y + n * a)], fill=(90, 60, 30, r.randint(10, 26)), width=1)
    return out


def _load_logo(card):
    f = getattr(card, "logo", None)
    if not f:
        return None
    try:
        if hasattr(f, "seek"):
            f.seek(0)
        data = f.read() if hasattr(f, "read") else None
        if not data:
            return None
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGBA")
        if hasattr(f, "seek"):
            f.seek(0)
        return img
    except Exception:
        return None


def _monogram(name, size, bg, fg):
    """Logo de repli : initiales dans un disque (si aucun logo n'est fourni)."""
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "N"
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=bg)
    f = font("Poppins-Bold", int(size * .42))
    d.text((size / 2, size / 2 + size * .03), initials, font=f, fill=fg, anchor="mm")
    return img


def _paste_logo(img, card, th, box, anchor="l"):
    """Place le logo (ou le monogramme) dans `box` = (x, y, w, h) ; renvoie sa largeur réelle."""
    x, y, bw, bh = box
    logo = _load_logo(card)
    if logo is None:
        logo = _monogram(card.company_name, min(bw, bh), th.accent, "#ffffff" if th.key != "pagne" else "#3a1d12")
    else:
        logo.thumbnail((bw, bh), Image.LANCZOS)
        if th.plate:
            pad = 14
            plate = Image.new("RGBA", (logo.width + pad * 2, logo.height + pad * 2), (0, 0, 0, 0))
            ImageDraw.Draw(plate).rounded_rectangle([0, 0, plate.width - 1, plate.height - 1], 18, fill="#ffffff")
            plate.alpha_composite(logo, (pad, pad))
            logo = plate
    px = x if anchor == "l" else x + (bw - logo.width) // 2
    img.alpha_composite(logo, (int(px), int(y + (bh - logo.height) // 2)))
    return logo.width


# --- Décors par modèle --------------------------------------------------------------

def _bg(th, side):
    img = Image.new("RGBA", (W, H), th.bg if side == "recto" else th.bg2)
    d = ImageDraw.Draw(img, "RGBA")
    k = th.key
    if k == "emeraude":
        if side == "recto":
            d.rectangle([0, 0, 46, H], fill="#16a34a")
            d.rectangle([46, 0, 56, H], fill="#14532d")
            d.ellipse([W - 260, -150, W + 120, 230], outline=(22, 163, 74, 60), width=26)
        else:
            d.rectangle([0, 0, W, 30], fill="#16a34a")
            d.rectangle([0, 30, W, 38], fill="#14532d")
            d.rectangle([0, H - 12, W, H], fill="#16a34a")
    elif k == "minuit":
        for i in range(-H, W, 16):
            d.line([(i, H), (i + H, 0)], fill=(255, 255, 255, 9), width=1)
        if side == "recto":
            d.rectangle([W - 18, 0, W, H], fill="#f28c28")
        else:
            d.rectangle([0, 0, 14, H], fill="#f28c28")
    elif k == "kraft":
        img = _grain(img.convert("RGB"), 13).convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        if side == "verso":
            d.rounded_rectangle([46, 46, W - 46, H - 46], 14, fill=(247, 237, 216, 255))
        _stitch(img, 24 if side == "recto" else 58)
    elif k == "pagne":
        if side == "recto":
            _wax_column(d, W - 190, W)
            d.rectangle([W - 196, 0, W - 190, H], fill="#3a1d12")
        else:
            _wax_column(d, 0, 96, tone="light")
            d.rectangle([96, 0, 102, H], fill="#b5532a")
    elif k == "ivoire":
        d.rectangle([26, 26, W - 26, H - 26], outline="#a8842f", width=3)
        d.rectangle([40, 40, W - 40, H - 40], outline="#a8842f", width=1)
        for cx, cy, a0 in ((26, 26, 0), (W - 26, 26, 90), (W - 26, H - 26, 180), (26, H - 26, 270)):
            d.pieslice([cx - 34, cy - 34, cx + 34, cy + 34], a0, a0 + 90, fill="#a8842f")
            d.pieslice([cx - 18, cy - 18, cx + 18, cy + 18], a0, a0 + 90, fill="#f8f2e2")
    elif k == "sauge":
        if side == "recto":
            d.ellipse([W - 360, -200, W + 140, 300], fill="#d8eadc")
            d.ellipse([W - 250, -120, W + 60, 190], fill="#bfdcc6")
            d.ellipse([-120, H - 140, 200, H + 180], fill="#d8eadc")
        else:
            d.ellipse([-160, H - 220, 260, H + 200], fill="#e1efe4")
            d.rectangle([0, 0, W, 14], fill="#1f6f4a")
    return img


def _stitch(img, inset):
    """Couture façon sellier : tirets réguliers autour de la carte."""
    d = ImageDraw.Draw(img, "RGBA")
    col = (96, 62, 30, 210)
    x0, y0, x1, y1 = inset, inset, W - inset, H - inset
    for x in range(x0, x1, 22):
        d.line([(x, y0), (min(x + 12, x1), y0)], fill=col, width=3)
        d.line([(x, y1), (min(x + 12, x1), y1)], fill=col, width=3)
    for y in range(y0, y1, 22):
        d.line([(x0, y), (x0, min(y + 12, y1))], fill=col, width=3)
        d.line([(x1, y), (x1, min(y + 12, y1))], fill=col, width=3)


def _wax_column(d, xa, xb, tone="dark"):
    """Bande de motifs « wax » : cercles concentriques et losanges."""
    cx = (xa + xb) // 2
    ring = ["#3a1d12", "#e0a030", "#fff1d6", "#b5532a", "#3a1d12"] if tone == "dark" else \
           ["#b5532a", "#e0a030", "#3a1d12", "#fff1d6", "#b5532a"]
    if tone == "dark":
        d.rectangle([xa, 0, xb, H], fill="#a2461f")
    else:
        d.rectangle([xa, 0, xb, H], fill="#f1e1c4")
    size = (xb - xa) // 2 - 6
    for cy in range(size + 6, H + size, size * 2 + 14):
        for r, c in zip((size, size * .8, size * .6, size * .38, size * .16), ring):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
        d.polygon([(cx, cy + size + 2), (cx + 9, cy + size + 8), (cx, cy + size + 14), (cx - 9, cy + size + 8)],
                  fill="#e0a030")


# --- Icônes de contact (dessinées, sans police d'icônes) --------------------------------

def _icon(d, kind, x, y, s, color):
    c = color
    if kind == "phone":
        d.rounded_rectangle([x + s * .25, y, x + s * .75, y + s], int(s * .12), outline=c, width=3)
        d.ellipse([x + s * .45, y + s * .8, x + s * .55, y + s * .9], fill=c)
    elif kind == "email":
        d.rounded_rectangle([x, y + s * .15, x + s, y + s * .85], 4, outline=c, width=3)
        d.line([(x + 2, y + s * .2), (x + s / 2, y + s * .55), (x + s - 2, y + s * .2)], fill=c, width=3)
    elif kind == "web":
        d.ellipse([x, y, x + s, y + s], outline=c, width=3)
        d.ellipse([x + s * .3, y, x + s * .7, y + s], outline=c, width=2)
        d.line([(x, y + s / 2), (x + s, y + s / 2)], fill=c, width=2)
    else:  # adresse : épingle
        d.ellipse([x + s * .15, y, x + s * .85, y + s * .7], outline=c, width=3)
        d.polygon([(x + s * .25, y + s * .55), (x + s * .75, y + s * .55), (x + s / 2, y + s)], fill=c)
        d.ellipse([x + s * .38, y + s * .23, x + s * .62, y + s * .47], fill=c)


def _vcard_qr(card, size, fg, pad=12):
    data = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{card.contact_name}", f"ORG:{card.company_name}"]
    for tag, val in (("TITLE", card.job_title), ("TEL", card.phone), ("EMAIL", card.email),
                     ("URL", card.website), ("ADR", f";;{card.address};;;;" if card.address else "")):
        if val:
            data.append(f"{tag}:{val}")
    data.append("END:VCARD")
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=0)
    qr.add_data("\n".join(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color=fg, back_color="white").convert("RGB").resize((size, size), Image.NEAREST)
    plate = Image.new("RGBA", (size + pad * 2, size + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([0, 0, plate.width - 1, plate.height - 1], 14, fill="#ffffff")
    plate.paste(img, (pad, pad))
    return plate


# --- Mise en page ---------------------------------------------------------------------

def _recto(img, card, th):
    d = ImageDraw.Draw(img, "RGBA")
    left, right = th.x0, W - th.x1
    maxw = right - left
    center = th.align == "center"
    tcol, scol = th.ink, th.soft
    if th.key == "kraft":
        tcol, scol = th.ink, th.soft
    logo_h = 150 if card.tagline else 170
    anchor = "m" if center else "l"
    _paste_logo(img, card, th, (left, 64, maxw, logo_h), anchor="c" if center else "l")
    fnt, lines = _fit_block(th.title, card.company_name, maxw, 66, 34, 2)
    y = 64 + logo_h + 46
    ax = (left + right) // 2 if center else left
    for line in lines:
        _text(d, (ax, y), line, fnt, tcol, anchor + "a", th.deboss)
        y += int(fnt.size * 1.18)
    if card.tagline:
        y += 14
        if center:
            d.line([(ax - 40, y), (ax + 40, y)], fill=th.accent, width=3)
        else:
            d.line([(left, y), (left + 80, y)], fill=th.accent, width=5)
        y += 22
        tf, tl = _fit_block(th.body, card.tagline, maxw, 30, 22, 2)
        for line in tl:
            _text(d, (ax, y), line, tf, scol, anchor + "a", th.deboss)
            y += int(tf.size * 1.4)


def _verso(img, card, th):
    d = ImageDraw.Draw(img, "RGBA")
    left, right = th.x0, W - th.x1
    center = th.align == "center"
    dark = th.key in ("minuit",)
    tcol, scol = th.ink, th.soft
    if th.key == "pagne":  # verso clair : texte sombre
        tcol, scol = "#3a1d12", "#7a4a33"
        left, right = 150, W - 70
    if th.key == "kraft":
        left, right = 110, W - 110
    show_qr = not center
    col_w = (right - left) - (190 if show_qr else 0)
    ax = (left + right) // 2 if center else left
    anchor = "m" if center else "l"
    y = 84 if th.key != "kraft" else 100
    nf, nl = _fit_block(th.title, card.contact_name, right - left, 54, 32, 1)
    _text(d, (ax, y), nl[0] if nl else "", nf, tcol, anchor + "a", th.deboss)
    y += int(nf.size * 1.25)
    if card.job_title:
        jf, jl = _fit_block(th.body, card.job_title.upper() if not center else card.job_title, right - left, 26, 18, 1)
        _text(d, (ax, y), jl[0], jf, th.accent if th.key != "kraft" else "#7a4b22", anchor + "a", th.deboss)
        y += int(jf.size * 1.5)
    y += 14
    d.line([(ax - (60 if center else 0), y), (ax + (60 if center else 90), y)], fill=th.accent, width=4)
    y += 34
    items = [("phone", card.phone), ("email", card.email), ("web", card.website), ("pin", card.address)]
    lf = font(th.body, 32 if th.body.startswith("Caladea") else 27)
    for kind, val in [i for i in items if i[1]]:
        lines = _wrap(val, lf, col_w - 52) if not center else [val]
        lines = lines[:2]
        if center:
            w = lf.getlength(lines[0])
            _text(d, (ax, y + 2), lines[0], lf, scol if kind != "web" else tcol, "ma", th.deboss)
            y += 46
            continue
        _icon(d, kind, left, y + 4, 30, th.accent if not dark else th.accent)
        for ln in lines:
            _text(d, (left + 52, y), ln, lf, tcol, "la", th.deboss)
            y += 38
        y += 14
    if show_qr:
        qr = _vcard_qr(card, 124, "#0f2a1c" if not dark else "#14284b")
        img.alpha_composite(qr, (right - qr.width, H - 64 - qr.height))


def _watermark(img):
    layer = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f = font("Poppins-Bold", 54)
    for yy in range(0, H * 2, 170):
        for xx in range(-200, W * 2, 420):
            d.text((xx + (yy // 170 % 2) * 210, yy), "APERÇU", font=f, fill=(120, 120, 120, 70))
    layer = layer.rotate(24, resample=Image.BICUBIC)
    layer = layer.crop((W // 2, H // 2, W // 2 + W, H // 2 + H))
    return Image.alpha_composite(img, layer)


def render_card(card, side="recto", scale=1.0, watermark=False) -> Image.Image:
    """Image RGB de la carte (`card` : BusinessCard ou tout objet avec les mêmes attributs)."""
    th = THEMES.get(card.theme) or THEMES["emeraude"]
    img = _bg(th, side)
    (_recto if side == "recto" else _verso)(img, card, th)
    if watermark:
        img = _watermark(img)
    img = img.convert("RGB")
    if scale != 1.0:
        img = img.resize((int(W * scale), int(H * scale)), Image.LANCZOS)
    return img


def png_bytes(card, side="recto", scale=1.0, watermark=False) -> bytes:
    buf = io.BytesIO()
    render_card(card, side, scale, watermark).save(buf, "PNG", dpi=(300, 300), optimize=True)
    return buf.getvalue()


def card_pdf(card) -> bytes:
    """PDF 85 × 55 mm : page 1 = recto, page 2 = verso (300 dpi)."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(85 * mm, 55 * mm))
    c.setTitle(f"Carte de visite — {card.company_name}")
    c.setAuthor("NovaTickets")
    for side in ("recto", "verso"):
        c.drawImage(ImageReader(render_card(card, side)), 0, 0, 85 * mm, 55 * mm)
        c.showPage()
    c.save()
    return buf.getvalue()


# --- Échantillons de modèles (vignettes du formulaire) ---------------------------------

SAMPLE = SimpleNamespace(
    company_name="Atelier Cotonou", contact_name="Awa Adjovi", job_title="Directrice artistique",
    phone="+229 01 97 12 34 56", email="awa@atelier-cotonou.bj", website="www.atelier-cotonou.bj",
    address="Rue des Cocotiers, Haie Vive, Cotonou", tagline="Le beau fait main, du Bénin au monde", logo=None,
)


@lru_cache(maxsize=32)
def sample_png(theme: str, side: str) -> bytes:
    return png_bytes(SimpleNamespace(**{**SAMPLE.__dict__, "theme": theme}), side, scale=.5)
