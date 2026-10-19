"""API publique des cartes de visite : rendu recto/verso, aperçu filigrané, miniatures, PDF et vCard."""
import io
from functools import lru_cache

from PIL import Image, ImageDraw
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .cardkit import W, H, CardData, get_font, open_logo, vcard_text as _vcard
from .cardstyles import TEMPLATES, TEMPLATE_CHOICES  # noqa: F401

COLORS = ["#059669", "#1d4e89", "#ea580c", "#7c3aed", "#be123c", "#0f172a"]
FINAL_SCALE = 3      # 3150 x 1800 rendu puis réduit à 2100 x 1200 (anticrénelage)
PREVIEW_SCALE = 1.5  # 1575 x 900 → 840 x 480
SAMPLE = dict(company="Afro Vibes Productions", tagline="Événements & spectacles", name="Koffi Ahouansou",
              title="Directeur général", phone="+229 97 00 00 00", email="contact@afrovibes.bj",
              website="www.afrovibes.bj", address="Rue des Cocotiers, Cotonou, Bénin", social="@afrovibes")


def data_from_card(card, logo=None):
    """CardData à partir d'un BusinessCard (ou d'un objet équivalent)."""
    return CardData(
        company=card.company_name, tagline=card.tagline, name=card.contact_name, title=card.job_title,
        phone=card.phone, email=card.email, website=card.website, address=card.address,
        social=getattr(card, "social", ""), template=getattr(card, "template", "atelier") or "atelier",
        color=card.color, logo=logo if logo is not None else (open_logo(card.logo) if card.logo else None)
        or open_logo(getattr(card.user, "org_logo", None)))


def render(data, side, scale):
    tpl = TEMPLATES.get(data.template, TEMPLATES["atelier"])
    return tpl[side](data, scale)


def vcard_text(card):
    return _vcard(data_from_card(card, logo=False))


def _resize(img, w):
    return img.resize((w, round(w * H / W)), Image.LANCZOS)


def _as_data(obj):
    return obj if isinstance(obj, CardData) else data_from_card(obj)


def final_image(card, side):
    return _resize(render(_as_data(card), side, FINAL_SCALE), 2100)


def watermark(img):
    """Filigrane « APERÇU » en diagonale : la carte ne peut pas servir sans paiement."""
    img = img.convert("RGBA")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    f = get_font("pop_bold", img.width * 0.05)
    d = ImageDraw.Draw(layer)
    text = "APERÇU · NovaTickets   "
    step_x, step_y = int(d.textlength(text, font=f)), int(img.width * 0.17)
    big = Image.new("RGBA", (img.width * 2, img.height * 2), (0, 0, 0, 0))
    bd = ImageDraw.Draw(big)
    for row, y in enumerate(range(0, big.height, step_y)):
        for x in range(-step_x, big.width, step_x):
            bd.text((x + (row % 2) * step_x // 2, y), text, font=f, fill=(15, 23, 42, 46))
    big = big.rotate(28, resample=Image.BICUBIC)
    ox, oy = (big.width - img.width) // 2, (big.height - img.height) // 2
    layer.paste(big.crop((ox, oy, ox + img.width, oy + img.height)))
    return Image.alpha_composite(img, layer).convert("RGB")


def _png(img, dpi=None):
    buf = io.BytesIO()
    img.save(buf, "PNG", **({"dpi": dpi} if dpi else {}))
    return buf.getvalue()


def _jpeg(img, q=82):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=q, optimize=True)
    return buf.getvalue()


# petit cache : la page de modification rafraîchit l'aperçu souvent
_CACHE = {}


def _cached(key, fn):
    if key not in _CACHE:
        if len(_CACHE) > 48:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = fn()
    return _CACHE[key]


def preview_png(data, side):
    """Aperçu (840 x 480) filigrané, sans valeur d'impression."""
    return _png(watermark(_resize(render(data, side, PREVIEW_SCALE), 840)))


def clean_preview_png(data, side):
    """Aperçu net pour la carte déjà payée (affichage à l'écran)."""
    return _png(_resize(render(data, side, PREVIEW_SCALE), 1050))


def card_png(card, side):
    """Fichier final haute définition (2100 x 1200, 600 dpi)."""
    return _png(final_image(card, side), dpi=(600, 600))


def sample_png(template, color, side="recto"):
    """Miniature d'un modèle avec des données d'exemple (liste de choix du formulaire)."""
    def make():
        d = CardData(template=template, color=color, **SAMPLE)
        return _png(_resize(render(d, side, 1), 420))
    return _cached(("thumb", template, color, side), make)


def card_pdf(card):
    """PDF 2 pages (recto puis verso), 3,5 x 2 pouces, prêt à imprimer."""
    pw, ph = 252, 144
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(pw, ph))
    c.setTitle(f"Carte de visite – {getattr(card, 'company_name', '')}")
    card = _as_data(card)
    for side in ("recto", "verso"):
        c.drawImage(ImageReader(io.BytesIO(_jpeg(final_image(card, side), 95))), 0, 0, width=pw, height=ph)
        c.showPage()
    c.save()
    return buf.getvalue()
