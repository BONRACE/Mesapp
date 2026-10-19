"""Boîte à outils de dessin des cartes de visite (Pillow) : toile, polices, icônes, QR, effets de papier.

Toutes les coordonnées sont « logiques » sur une carte de 1050 x 600 (3,5 x 2 pouces à 300 dpi).
La toile (Cv) les multiplie par l'échelle de rendu : 1 pour une miniature, 3 pour le fichier final.
"""
import math
import random
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import qrcode
from django.conf import settings
from PIL import Image, ImageChops, ImageDraw, ImageFont

W, H = 1050, 600
FONT_DIR = Path(settings.BASE_DIR) / "static" / "fonts"
FONTS = {
    "inter": "Inter-Regular.otf", "inter_semi": "Inter-SemiBold.otf", "inter_bold": "Inter-Bold.otf",
    "pop": "Poppins-Regular.ttf", "pop_med": "Poppins-Medium.ttf", "pop_semi": "Poppins-SemiBold.ttf",
    "pop_bold": "Poppins-Bold.ttf",
    "play": "PlayfairDisplay-Bold.ttf", "play_med": "PlayfairDisplay-Medium.ttf",
    "script": "Caveat-Bold.ttf",
    "corm": "CormorantGaramond-SemiBold.ttf", "corm_med": "CormorantGaramond-Medium.ttf",
    "corm_it": "CormorantGaramond-MediumItalic.ttf",
}


@lru_cache(maxsize=256)
def get_font(key, px):
    return ImageFont.truetype(str(FONT_DIR / FONTS[key]), max(4, int(px)))


# ------------------------------------------------------------------ couleurs
def hex_rgb(value, default=(5, 150, 105)):
    try:
        v = value.lstrip("#")
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return default


def mix(a, b, t):
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def lum(c):
    return (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) / 255


def rgba(c, a):
    return (c[0], c[1], c[2], int(255 * a))


def hexstr(c):
    return "#%02x%02x%02x" % tuple(c)


# ------------------------------------------------------------------ données d'une carte
@dataclass
class CardData:
    company: str = ""
    tagline: str = ""
    name: str = ""
    title: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    address: str = ""
    social: str = ""
    template: str = "atelier"
    color: str = "#059669"
    logo: object = None  # image PIL RGBA ou None

    @property
    def accent(self):
        return hex_rgb(self.color)

    @property
    def seed(self):
        return zlib.crc32((self.company + self.name).encode("utf-8")) & 0xFFFF

    @property
    def initials(self):
        words = [w for w in self.company.split() if w[:1].isalnum()]
        return ("".join(w[0] for w in words[:2]) or self.name[:1] or "?").upper()

    @property
    def website_url(self):
        site = self.website.strip()
        if site and not site.lower().startswith(("http://", "https://")):
            site = "https://" + site
        return site

    @property
    def place(self):
        """Ville / pays : dernier morceau de l'adresse (affiché sur le tampon)."""
        return self.address.split(",")[-1].strip() if self.address.strip() else ""

    def rows(self):
        items = [("phone", self.phone), ("mail", self.email), ("web", self.website),
                 ("pin", self.address), ("at", self.social)]
        return [(k, v.strip()) for k, v in items if v and v.strip()]


def _esc(value):
    return (value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def vcard_text(c):
    parts = c.name.split()
    family = parts[-1] if parts else ""
    given = " ".join(parts[:-1])
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"FN:{_esc(c.name)}", f"N:{_esc(family)};{_esc(given)};;;",
             f"ORG:{_esc(c.company)}"]
    if c.title:
        lines.append(f"TITLE:{_esc(c.title)}")
    if c.phone:
        lines.append(f"TEL;TYPE=CELL:{_esc(c.phone)}")
    if c.email:
        lines.append(f"EMAIL:{_esc(c.email)}")
    if c.website:
        lines.append(f"URL:{c.website_url}")
    if c.address:
        lines.append(f"ADR;TYPE=WORK:;;{_esc(c.address)};;;;")
    if c.tagline:
        lines.append(f"NOTE:{_esc(c.tagline)}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def open_logo(f):
    """Ouvre un logo (fichier du modèle ou fichier envoyé) ; rogne les marges transparentes."""
    if not f:
        return None
    try:
        if hasattr(f, "path"):
            im = Image.open(f.path)
        else:
            f.seek(0)
            im = Image.open(f)
        im = im.convert("RGBA")
        im.thumbnail((1200, 1200))
        box = im.getchannel("A").getbbox()
        return im.crop(box) if box else im
    except Exception:
        return None


# ------------------------------------------------------------------ papier et fonds
@lru_cache(maxsize=3)
def kraft_paper(pw, ph, base):
    """Papier kraft : dégradé doux, grain, fibres et bords assombris (identique à chaque rendu)."""
    rng = random.Random(7)
    img = Image.new("RGB", (pw, ph), base)
    shade = Image.linear_gradient("L").resize((pw, ph)).point(lambda v: int(v * 0.09))
    img = Image.composite(Image.new("RGB", (pw, ph), (70, 48, 30)), img, shade)
    gw, gh = max(1, pw // 2), max(1, ph // 2)
    grain = Image.frombytes("L", (gw, gh), rng.randbytes(gw * gh)).resize((pw, ph), Image.BICUBIC)
    grain = grain.point(lambda v: 128 + (v - 128) // 8)
    img = ImageChops.add(img, Image.merge("RGB", (grain, grain, grain)), 1.0, -128)
    fib = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    d = ImageDraw.Draw(fib)
    k = pw / W
    for _ in range(260):
        x, y = rng.uniform(0, pw), rng.uniform(0, ph)
        a, ln = rng.uniform(0, math.pi), rng.uniform(10, 38) * k
        col = (60, 40, 22, rng.randint(16, 34)) if rng.random() < 0.6 else (255, 240, 215, rng.randint(14, 30))
        d.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln)], fill=col, width=max(1, round(k * 0.9)))
    img = Image.alpha_composite(img.convert("RGBA"), fib).convert("RGB")
    vig = Image.radial_gradient("L").resize((pw, ph)).point(lambda v: int(max(0, v - 90) * 0.34))
    return Image.composite(Image.new("RGB", (pw, ph), (58, 38, 22)), img, vig)


def vgradient(pw, ph, top, bottom):
    mask = Image.linear_gradient("L").resize((pw, ph))
    return Image.composite(Image.new("RGB", (pw, ph), bottom), Image.new("RGB", (pw, ph), top), mask)


def qr_image(text, px, fg, bg):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=0)
    qr.add_data(text)
    qr.make(fit=True)
    n = qr.modules_count
    box = max(1, px // n)
    made = qr.make_image(fill_color=hexstr(fg), back_color=hexstr(bg))
    im = (made.get_image() if hasattr(made, "get_image") else made._img).convert("RGB")
    return im.resize((n * box, n * box), Image.NEAREST)


# ------------------------------------------------------------------ la toile
class Cv:
    def __init__(self, s, bg):
        self.s = s
        self.pw, self.ph = round(W * s), round(H * s)
        self.img = bg.copy() if isinstance(bg, Image.Image) else Image.new("RGB", (self.pw, self.ph), bg)
        self.d = ImageDraw.Draw(self.img, "RGBA")

    # -- formes
    def _pts(self, pts):
        return [(x * self.s, y * self.s) for x, y in pts]

    def _w(self, w):
        return max(1, round(w * self.s))

    def rect(self, b, fill=None, outline=None, w=0, r=0):
        box = [v * self.s for v in b]
        kw = dict(fill=fill, outline=outline, width=self._w(w) if outline else 0)
        if r:
            self.d.rounded_rectangle(box, r * self.s, **kw)
        else:
            self.d.rectangle(box, **kw)

    def circle(self, cx, cy, r, fill=None, outline=None, w=0):
        self.ellipse((cx - r, cy - r, cx + r, cy + r), fill, outline, w)

    def ellipse(self, b, fill=None, outline=None, w=0):
        self.d.ellipse([v * self.s for v in b], fill=fill, outline=outline, width=self._w(w) if outline else 0)

    def line(self, pts, fill, w=1):
        self.d.line(self._pts(pts), fill=fill, width=self._w(w), joint="curve")

    def poly(self, pts, fill=None, outline=None):
        self.d.polygon(self._pts(pts), fill=fill, outline=outline)

    def diamond(self, cx, cy, r, fill):
        self.poly([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill)

    def star(self, cx, cy, r, fill):
        pts = []
        for i in range(10):
            a = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.42
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        self.poly(pts, fill)

    def hand_line(self, x0, y0, x1, y1, fill, w=2, amp=1.2, seed=0):
        """Trait légèrement irrégulier, comme tracé à la main."""
        rng = random.Random(seed)
        ln = math.hypot(x1 - x0, y1 - y0) or 1
        n = max(6, int(ln / 26))
        nx, ny = -(y1 - y0) / ln, (x1 - x0) / ln
        off, pts = 0.0, []
        for i in range(n + 1):
            t = i / n
            off = off * 0.45 + rng.uniform(-amp, amp)
            o = 0 if i in (0, n) else off
            pts.append((x0 + (x1 - x0) * t + nx * o, y0 + (y1 - y0) * t + ny * o))
        self.line(pts, fill, w)
        for px, py in (pts[0], pts[-1]):
            self.circle(px, py, w / 2, fill=fill)

    def dotted(self, x0, x1, y, fill, gap=11, r=1.4):
        x = x0
        while x <= x1:
            self.circle(x, y, r, fill=fill)
            x += gap

    # -- texte (y = ligne de base)
    def font(self, key, size):
        return get_font(key, round(size * self.s))

    def tw(self, text, key, size, track=0):
        f = self.font(key, size)
        if track:
            return sum(self.d.textlength(ch, font=f) for ch in text) / self.s + track * max(0, len(text) - 1)
        return self.d.textlength(text, font=f) / self.s

    def text(self, x, y, text, key, size, fill, align="l", track=0):
        f = self.font(key, size)
        if track:
            total = self.tw(text, key, size, track)
            cx = x - (total if align == "r" else total / 2 if align == "m" else 0)
            for ch in text:
                self.d.text((cx * self.s, y * self.s), ch, font=f, fill=fill, anchor="ls")
                cx += self.d.textlength(ch, font=f) / self.s + track
        else:
            self.d.text((x * self.s, y * self.s), text, font=f, fill=fill, anchor={"l": "ls", "m": "ms", "r": "rs"}[align])

    def text_rot(self, cx, cy, text, key, size, fill, angle):
        """Texte centré en (cx, cy), tourné de `angle` degrés (sens antihoraire)."""
        f = self.font(key, size)
        l, t, r, b = f.getbbox(text)
        layer = Image.new("RGBA", (r - l + 12, b - t + 12), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((6 - l, 6 - t), text, font=f, fill=fill)
        layer = layer.rotate(angle, expand=True, resample=Image.BICUBIC)
        self.img.paste(layer, (round(cx * self.s - layer.width / 2), round(cy * self.s - layer.height / 2)), layer)

    def arc_text(self, cx, cy, r, text, key, size, fill, bottom=False, track=3):
        """Texte courbé sur un cercle (r = rayon de la ligne de base)."""
        f = self.font(key, size)
        widths = [self.d.textlength(ch, font=f) for ch in text]
        tp = track * self.s
        total = sum(widths) + tp * (len(text) - 1)
        rad = r * self.s
        pos = -total / 2
        T = int(size * self.s * 2.6) + 6
        for ch, w in zip(text, widths):
            delta = math.degrees((pos + w / 2) / rad)
            pos += w + tp
            tile = Image.new("RGBA", (T, T), (0, 0, 0, 0))
            ImageDraw.Draw(tile).text((T / 2, T / 2), ch, font=f, fill=fill, anchor="ms")
            ang = (90 - delta) if bottom else (-90 + delta)
            tile = tile.rotate(delta if bottom else -delta, resample=Image.BICUBIC)
            px = cx * self.s + rad * math.cos(math.radians(ang))
            py = cy * self.s + rad * math.sin(math.radians(ang))
            self.img.paste(tile, (round(px - T / 2), round(py - T / 2)), tile)

    def arc_span(self, text, key, size, r, track=3):
        """Angle (degrés) occupé par un texte courbé."""
        return math.degrees(self.tw(text, key, size, track) / r)

    # -- images
    def paste_fit(self, im, cx, cy, max_w, max_h):
        """Colle `im` (RGBA) centrée en (cx, cy), contenue dans max_w x max_h (unités logiques)."""
        k = min(max_w * self.s / im.width, max_h * self.s / im.height)
        small = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        self.img.paste(small, (round(cx * self.s - small.width / 2), round(cy * self.s - small.height / 2)), small)

    def qr(self, cx, cy, size, text, fg, bg, pad=16):
        px = round((size - 2 * pad) * self.s)
        im = qr_image(text, px, fg, bg)
        self.img.paste(im, (round(cx * self.s - im.width / 2), round(cy * self.s - im.height / 2)))

    # -- effet tampon
    def snapshot(self, box):
        x0, y0, x1, y1 = [round(v * self.s) for v in box]
        return self.img.crop((x0, y0, x1, y1)), (x0, y0)

    def erode(self, snap, seed, density=1.5):
        """Efface de petits éclats d'encre (aspect tampon) en restaurant le papier d'avant."""
        orig, (x0, y0) = snap
        w, h = orig.size
        gw, gh = max(1, w // 3), max(1, h // 3)
        noise = Image.frombytes("L", (gw, gh), random.Random(seed).randbytes(gw * gh))
        thr = int(255 - 255 * 0.075 * density)
        mask = noise.point(lambda v: 255 if v > thr else 0).resize((w, h), Image.NEAREST)
        cur = self.img.crop((x0, y0, x0 + w, y0 + h))
        self.img.paste(Image.composite(orig, cur, mask), (x0, y0))


# ------------------------------------------------------------------ mise en page de texte
def wrap(cv, text, key, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if cv.tw(trial, key, size) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def ellipsize(cv, text, key, size, max_w, track=0):
    if cv.tw(text, key, size, track) <= max_w:
        return text
    while text and cv.tw(text + "…", key, size, track) > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def fit_name(cv, text, key, max_size, min_size, max_w, max_lines=2):
    """Plus grande taille pour laquelle le nom tient sur 1 ou 2 lignes ; sinon coupe avec « … »."""
    text = text.strip() or " "
    size = max_size
    while size >= min_size:
        lines = wrap(cv, text, key, size, max_w)
        if len(lines) <= max_lines and all(cv.tw(ln, key, size) <= max_w for ln in lines):
            return lines, size
        size -= 2
    lines = wrap(cv, text, key, min_size, max_w)[:max_lines] or [text]
    lines[-1] = ellipsize(cv, lines[-1], key, min_size, max_w)
    return [ellipsize(cv, ln, key, min_size, max_w) for ln in lines], min_size


def fit_line(cv, text, key, max_size, min_size, max_w, track=0):
    size = max_size
    while size > min_size and cv.tw(text, key, size, track) > max_w:
        size -= 1
    return ellipsize(cv, text, key, size, max_w, track), size


# ------------------------------------------------------------------ icônes de contact
def icon(cv, kind, cx, cy, size, color, w=None):
    w = w or max(1.7, size * 0.085)
    if kind == "phone":
        bw, bh = size * 0.54, size * 0.94
        cv.rect((cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2), outline=color, w=w, r=size * 0.13)
        cv.line([(cx - bw * 0.2, cy - bh * 0.33), (cx + bw * 0.2, cy - bh * 0.33)], color, w)
        cv.circle(cx, cy + bh * 0.32, size * 0.05 + 0.5, fill=color)
    elif kind == "mail":
        mw, mh = size * 1.02, size * 0.74
        cv.rect((cx - mw / 2, cy - mh / 2, cx + mw / 2, cy + mh / 2), outline=color, w=w, r=size * 0.1)
        cv.line([(cx - mw / 2 + 1.5, cy - mh / 2 + 2), (cx, cy + mh * 0.1), (cx + mw / 2 - 1.5, cy - mh / 2 + 2)], color, w)
    elif kind == "web":
        r = size * 0.47
        cv.circle(cx, cy, r, outline=color, w=w)
        cv.ellipse((cx - r * 0.46, cy - r, cx + r * 0.46, cy + r), outline=color, w=w)
        cv.line([(cx - r, cy), (cx + r, cy)], color, w)
    elif kind == "pin":
        r, hy = size * 0.3, cy - size * 0.13
        cv.circle(cx, hy, r, outline=color, w=w)
        cv.line([(cx - r * 0.86, hy + r * 0.55), (cx, cy + size * 0.5), (cx + r * 0.86, hy + r * 0.55)], color, w)
        cv.circle(cx, hy, size * 0.075, fill=color)
    else:  # "at" : @
        cv.text(cx, cy + size * 0.36, "@", "inter_semi", size * 1.02, color, "m")


def draw_rows(cv, rows, x, y, pitch, size, key, text_color, icon_color, max_w, sep=None, sep_dotted=False):
    """Liste de coordonnées (icône + texte) ; retourne le y suivant. `y` = ligne de base de la 1re ligne."""
    for kind, text in rows:
        icon(cv, kind, x + 14, y - size * 0.34, 25, icon_color)
        tx = x + 52
        if kind == "pin":
            lines = wrap(cv, text, key, size, max_w - 52)[:2] or [text]
            if len(lines) == 2:
                lines[1] = ellipsize(cv, lines[1], key, size, max_w - 52)
            for i, ln in enumerate(lines):
                cv.text(tx, y + i * size * 1.28, ellipsize(cv, ln, key, size, max_w - 52), key, size, text_color)
            y += (len(lines) - 1) * size * 1.28
        else:
            cv.text(tx, y, ellipsize(cv, text, key, size, max_w - 52), key, size, text_color)
        if sep is not None:
            sy = y + pitch * 0.36
            if sep_dotted:
                cv.dotted(x + 52, x + max_w, sy, sep)
            else:
                cv.line([(x + 52, sy), (x + max_w, sy)], sep, 1)
        y += pitch
    return y


def medallion(cv, cx, cy, r, c, fill, ring, text_color, key="pop_semi", ring_w=3):
    """Pastille ronde : logo si fourni, sinon initiales."""
    cv.circle(cx, cy, r, fill=fill)
    if ring:
        cv.circle(cx, cy, r, outline=ring, w=ring_w)
    if c.logo is not None:
        cv.paste_fit(c.logo, cx, cy, r * 1.35, r * 1.35)
    else:
        size = r * (1.0 if len(c.initials) < 2 else 0.84)
        cv.text(cx, cy + size * 0.35, c.initials, key, size, text_color, "m")
