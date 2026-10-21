"""Génère le logo PROVISOIRE static/img/logo.png (+ logo-mark.png).

Remplacez simplement ces fichiers par votre vrai logo : aucun code à modifier.
Usage : python scripts/make_placeholder_logo.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
NAVY, ORANGE = (20, 40, 75, 255), (242, 140, 40, 255)
S = 4  # sur-échantillonnage


def draw_mark(size: int) -> Image.Image:
    """Lettre « N » en forme de fusée : barres marine, diagonale orange, flamme."""
    big = size * S
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = big / 100
    d.rounded_rectangle([14 * u, 20 * u, 30 * u, 86 * u], radius=4 * u, fill=NAVY)          # barre gauche
    d.rounded_rectangle([70 * u, 14 * u, 86 * u, 80 * u], radius=4 * u, fill=NAVY)          # barre droite
    d.polygon([(14 * u, 22 * u), (30 * u, 22 * u), (86 * u, 78 * u), (70 * u, 78 * u)], fill=NAVY)  # diagonale
    d.polygon([(30 * u, 22 * u), (44 * u, 22 * u), (86 * u, 64 * u), (86 * u, 78 * u), (70 * u, 78 * u)], fill=ORANGE)
    d.polygon([(70 * u, 14 * u), (96 * u, 2 * u), (86 * u, 30 * u)], fill=ORANGE)           # nez de fusée
    d.polygon([(14 * u, 86 * u), (30 * u, 86 * u), (22 * u, 99 * u)], fill=ORANGE)          # flamme
    return img.resize((size, size), Image.LANCZOS)


def main():
    out = ROOT / "static" / "img"
    out.mkdir(parents=True, exist_ok=True)
    mark = draw_mark(220)
    mark.save(out / "logo-mark.png")
    font_b = ImageFont.truetype(str(ROOT / "static/fonts/Poppins-Bold.ttf"), 78 * S)
    font_s = ImageFont.truetype(str(ROOT / "static/fonts/Poppins-Medium.ttf"), 34 * S)
    W, H = 980, 240
    canvas = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    d.text((290 * S, 30 * S), "NOVA", font=font_b, fill=NAVY)
    d.text((290 * S + d.textlength("NOVA ", font=font_b), 30 * S), "TICKETS", font=font_b, fill=ORANGE)
    d.text((294 * S, 150 * S), "BILLETTERIE EN LIGNE", font=font_s, fill=(90, 105, 130, 255))
    canvas = canvas.resize((W, H), Image.LANCZOS)
    canvas.alpha_composite(mark, (30, 10))
    canvas.save(out / "logo.png")
    print("Logo provisoire écrit dans", out)


if __name__ == "__main__":
    main()
