"""Images générées pour l'e-mail de reçu : signature de l'organisateur et tampon « vérifié par »."""
import io
import math

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

FONTS = settings.BASE_DIR / "static" / "fonts"
NAVY = (20, 40, 75, 255)
GREEN = (21, 128, 61, 255)


def signature_png(name: str) -> bytes:
    """Signature manuscrite stylisée (italique) avec un paraphe."""
    S, W, H = 3, 420, 120
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = 54
    font = ImageFont.truetype(str(FONTS / "Caladea-BoldItalic.ttf"), size * S)
    while d.textlength(name, font=font) > (W - 30) * S and size > 20:
        size -= 2
        font = ImageFont.truetype(str(FONTS / "Caladea-BoldItalic.ttf"), size * S)
    d.text((10 * S, 22 * S), name, font=font, fill=NAVY)
    # paraphe : courbe sous la signature
    pts = [(10 * S + i * 3 * S, (96 + 7 * math.sin(i / 5.0)) * S) for i in range(0, 120)]
    pts = [p for p in pts if p[0] < (W - 20) * S]
    d.line(pts, fill=NAVY, width=2 * S, joint="curve")
    out = io.BytesIO()
    img.resize((W, H), Image.LANCZOS).save(out, format="PNG")
    return out.getvalue()


def stamp_png(label_top="VÉRIFIÉ PAR", label_bottom="NOVATICKETS") -> bytes:
    """Tampon circulaire vert légèrement incliné."""
    S, N = 3, 150
    img = Image.new("RGBA", (N * S, N * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for inset, width in ((6, 4), (14, 2)):
        d.ellipse([inset * S, inset * S, (N - inset) * S, (N - inset) * S], outline=GREEN, width=width * S)
    f1 = ImageFont.truetype(str(FONTS / "Poppins-Bold.ttf"), 15 * S)
    f2 = ImageFont.truetype(str(FONTS / "Poppins-Bold.ttf"), 13 * S)
    for text, font, y in ((label_top, f1, 42), (label_bottom, f2, 88)):
        w = d.textlength(text, font=font)
        d.text(((N * S - w) / 2, y * S), text, font=font, fill=GREEN)
    # coche
    d.line([(52 * S, 70 * S), (68 * S, 80 * S), (98 * S, 60 * S)], fill=GREEN, width=5 * S, joint="curve")
    img = img.rotate(12, resample=Image.BICUBIC, expand=False).resize((N, N), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
