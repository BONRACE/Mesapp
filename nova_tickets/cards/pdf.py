"""Carte de visite en PDF (reportlab), au format carte (88,9 × 50,8 mm), prête à imprimer.

Styles « Pagne » : recto (bande de motif wax) + verso (bandeau, contacts, cadre QR « Scannez-moi ») — « Pagne verso » = verso seul.
Autres styles : recto en aplat de la couleur choisie + même verso, avec la couleur de la carte.
Toutes les mesures sont en « unités » = 1 % de la largeur de la carte, comme la carte affichée à l'écran.
"""
import io
import math

from django.conf import settings
from orders.services import qr_png
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit

from .models import BusinessCard
from .palettes import PALETTES, rgb

PAGE_W, PAGE_H = 252.0, 144.0          # 3,5 × 2 pouces
U = PAGE_W / 100                       # points par unité
H_UNITS = PAGE_H / U


def _mix(a, b, t):
    ca, cb = HexColor(a), HexColor(b)
    return Color(ca.red * (1 - t) + cb.red * t, ca.green * (1 - t) + cb.green * t, ca.blue * (1 - t) + cb.blue * t)


class _Painter:
    def __init__(self, c, pal):
        self.c, self.pal = c, pal
        self.base, self.dark, self.tint, self.accent = (HexColor(pal[k]) for k in ("base", "dark", "tint", "accent"))
        self.paper, self.ink = HexColor(pal["paper"]), HexColor(pal["ink"])
        self.role = _mix(pal["base"], pal["dark"], .55)

    # --- repères : coordonnées « CSS » (origine en haut à gauche, en unités) -> points PDF
    def x(self, v):
        return v * U

    def y(self, v):
        return PAGE_H - v * U

    def rect(self, x, y, w, h, color, radius=0):
        self.c.setFillColor(color)
        if radius:
            self.c.roundRect(self.x(x), self.y(y + h), w * U, h * U, radius * U, fill=1, stroke=0)
        else:
            self.c.rect(self.x(x), self.y(y + h), w * U, h * U, fill=1, stroke=0)

    def circle(self, cx, cy, r, color):
        self.c.setFillColor(color)
        self.c.circle(cx, cy, r, fill=1, stroke=0)

    def poly(self, pts, color):
        p = self.c.beginPath()
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        p.close()
        self.c.setFillColor(color)
        self.c.drawPath(p, fill=1, stroke=0)

    # --- motif « pagne »
    def pattern(self, x, y, w, h, tile):
        c = self.c
        c.saveState()
        p = c.beginPath()
        p.rect(self.x(x), self.y(y + h), w * U, h * U)
        c.clipPath(p, stroke=0, fill=0)
        self.rect(x, y, w, h, self.base)
        s = tile * U
        k = s / 250
        for ix in range(math.ceil(w * U / s) + 1):
            for iy in range(math.ceil(h * U / s) + 1):
                ox, oy = self.x(x) + ix * s, self.y(y) - iy * s       # coin haut-gauche de la tuile (PDF)

                def P(tx, ty):
                    return ox + tx * k, oy - ty * k
                for tx in (0, 125, 250):
                    for ty in (0, 125, 250):
                        cx, cy = P(tx, ty)
                        self.circle(cx, cy, 5 * k, self.tint)
                for tx, ty in ((62, 62), (187, 187)):
                    cx, cy = P(tx, ty)
                    for r, col in ((52, self.accent), (40, self.dark), (27, self.tint), (13, self.base)):
                        self.circle(cx, cy, r * k, col)
                for tx, ty in ((187, 62), (62, 187)):
                    cx, cy = P(tx, ty)
                    for r, col in ((50, self.dark), (36, self.tint), (22, self.accent)):
                        self.poly([(cx, cy + r * k), (cx + r * k, cy), (cx, cy - r * k), (cx - r * k, cy)], col)
                    self.circle(cx, cy, 7 * k, self.dark)
        c.restoreState()

    def teeth_v(self, x, y0, y1):
        t = 2.2 * U
        yy = self.y(y0)
        while yy > self.y(y1):
            self.poly([(self.x(x), yy), (self.x(x) + t, yy - t), (self.x(x), yy - t * 2)], self.accent)
            yy -= t * 2

    def teeth_h(self, y, x0, x1):
        w = 4 * U
        xx = self.x(x0)
        while xx < self.x(x1):
            self.poly([(xx, self.y(y)), (xx + w, self.y(y)), (xx + w / 2, self.y(y) - 2 * U)], self.accent)
            xx += w

    def dash(self, x, y, centered=False):
        w1, w2, gap = 7, 3.4, 1
        if centered:
            x = x - (w1 + gap + w2) / 2
        self.rect(x, y, w1, .9, self.accent, .45)
        self.rect(x + w1 + gap, y, w2, .9, self.base, .45)

    def text(self, x, y, s, size_u, font="Helvetica", color=None, center=False):
        self.c.setFillColor(color or self.ink)
        self.c.setFont(font, size_u * U)
        (self.c.drawCentredString if center else self.c.drawString)(self.x(x), self.y(y), s)

    def fit(self, s, font, size_u, max_w_u):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        while size_u > 2 and stringWidth(s, font, size_u * U) > max_w_u * U:
            size_u -= .2
        return size_u

    # --- petites icônes de contact (traits fins, couleur du rôle)
    def icon(self, kind, x, y, s):
        c = self.c
        c.saveState()
        c.setStrokeColor(self.role)
        c.setFillColor(self.role)
        c.setLineWidth(.45)
        X, Y, S = self.x(x), self.y(y), s * U
        if kind == "phone":
            c.roundRect(X + S * .25, Y - S, S * .5, S, S * .1, fill=0, stroke=1)
            c.circle(X + S * .5, Y - S * .85, S * .04, fill=1, stroke=0)
        elif kind == "mail":
            c.rect(X, Y - S * .85, S, S * .7, fill=0, stroke=1)
            c.line(X, Y - S * .15, X + S / 2, Y - S * .55)
            c.line(X + S, Y - S * .15, X + S / 2, Y - S * .55)
        elif kind == "web":
            c.circle(X + S / 2, Y - S / 2, S * .48, fill=0, stroke=1)
            c.ellipse(X + S * .28, Y - S * .98, X + S * .72, Y - S * .02, fill=0, stroke=1)
            c.line(X + S * .02, Y - S / 2, X + S * .98, Y - S / 2)
        elif kind == "pin":
            c.circle(X + S / 2, Y - S * .38, S * .3, fill=0, stroke=1)
            c.line(X + S * .27, Y - S * .6, X + S / 2, Y - S)
            c.line(X + S * .73, Y - S * .6, X + S / 2, Y - S)
        else:  # linkedin
            c.setFont("Helvetica-Bold", S * .9)
            c.drawString(X, Y - S * .8, "in")
        c.restoreState()

    def photo(self, card, x, y, size, radius):
        c = self.c
        c.saveState()
        p = c.beginPath()
        p.roundRect(self.x(x), self.y(y + size), size * U, size * U, radius * U)
        c.clipPath(p, stroke=0, fill=0)
        done = False
        photo = card.photo
        if photo:
            try:
                c.drawImage(ImageReader(photo.path), self.x(x), self.y(y + size), size * U, size * U, preserveAspectRatio=True, anchor="c", mask="auto")
                done = True
            except Exception:
                pass
        if not done:
            self.rect(x, y, size, size, white)
            self.text(x + size / 2, y + size * .64, card.initials, size * .34, "Helvetica-Bold", self.base, center=True)
        c.restoreState()
        c.setStrokeColor(_mix(self.pal["base"], "#ffffff", .75))
        c.setLineWidth(.6)
        c.roundRect(self.x(x), self.y(y + size), size * U, size * U, radius * U, fill=0, stroke=1)

    # --- faces
    def front_wax(self, card):
        self.rect(0, 0, 100, H_UNITS, self.paper)
        self.pattern(0, 0, 31, H_UNITS, 15.5)
        self.rect(31, 0, 1.5, H_UNITS, self.dark)
        self.teeth_v(32.5, 0, H_UNITS)
        self._front_text(card, left=40, color=self.ink, dark_bg=False)

    def front_plain(self, card):
        self.rect(0, 0, 100, H_UNITS, self.base)
        self.c.saveState()
        self.c.setFillColor(Color(1, 1, 1, alpha=.1))
        self.c.circle(self.x(92), self.y(-6), 46 * U / 1.2, fill=1, stroke=0)
        self.c.circle(self.x(-4), self.y(H_UNITS + 4), 30 * U / 1.2, fill=1, stroke=0)
        self.c.restoreState()
        lum = .299 * self.base.red + .587 * self.base.green + .114 * self.base.blue
        self._front_text(card, left=8, color=self.ink if lum > .72 else white, dark_bg=lum <= .72)

    def _front_text(self, card, left, color, dark_bg):
        width = 100 - left - 5
        name_size = 8.2 if left > 20 else 8.6
        name_lines = simpleSplit(card.full_name, "Helvetica-Bold", name_size * U, width * U)[:2]
        role_lines = simpleSplit(card.job_title, "Helvetica", 3.6 * U, width * U)[:1] if card.job_title else []
        co_lines = simpleSplit(card.company, "Helvetica", 3 * U, width * U)[:1] if card.company else []
        total = 15 + 1.8 + len(name_lines) * name_size * 1.1 + 1.8 + .9 + (1.8 + 3.6 if role_lines else 0) + (1.2 + 3 if co_lines else 0)
        y = (H_UNITS - total) / 2
        self.photo(card, left, y, 15, 2.2)
        y += 15 + 1.8
        for line in name_lines:
            y += name_size * .9
            self.text(left, y, line, name_size, "Helvetica-Bold", color)
            y += name_size * .2
        y += 1.8
        self.dash(left, y)
        y += .9
        if role_lines:
            y += 1.8 + 3.2
            self.text(left, y, role_lines[0], 3.6, "Helvetica", white if dark_bg else self.role)
            y += .4
        if co_lines:
            y += 1.2 + 2.6
            self.text(left, y, co_lines[0], 3, "Helvetica", color)

    def back(self, card, pattern):
        self.rect(0, 0, 100, H_UNITS, self.paper)
        if pattern:
            self.pattern(0, 0, 100, 15.5, 31)
            self.rect(0, 15.5, 100, 1.2, self.dark)
            self.teeth_h(16.7, 0, 100)
        else:
            self.rect(0, 0, 100, 15.5, self.base)
            self.rect(0, 15.5, 100, 1.2, self.accent)
        # identité
        name_size = self.fit(card.full_name, "Helvetica-Bold", 5.8, 60)
        self.text(6, 21.5 + name_size * .85, card.full_name, name_size, "Helvetica-Bold")
        y = 21.5 + name_size * 1.05 + .2
        if card.job_title:
            self.text(6, y + 3.0, card.job_title[:60], self.fit(card.job_title, "Helvetica", 3.2, 60), "Helvetica", self.role)
        y += 3.2 * 1.25 + 1.3
        site = card.website.replace("https://", "").replace("http://", "").rstrip("/")
        for kind, value in (("phone", card.phone), ("mail", card.email), ("web", site), ("linkedin", "LinkedIn" if card.linkedin else ""), ("pin", card.city)):
            if not value:
                continue
            self.icon(kind, 6, y, 3.1)
            self.text(10.2, y + 2.55, value, self.fit(value, "Helvetica", 2.7, 56), "Helvetica")
            y += 4.2
        # cadre QR
        qx, qy, qs = 70, 21.5, 24
        self.c.setStrokeColor(self.base)
        self.c.setFillColor(white)
        self.c.setLineWidth(.9 * U)
        self.c.roundRect(self.x(qx + .45), self.y(qy + qs - .45), (qs - .9) * U, (qs - .9) * U, 2.2 * U, fill=1, stroke=1)
        if card.is_active:
            png = qr_png(card.public_url, rgb(card.theme))
            self.c.drawImage(ImageReader(io.BytesIO(png)), self.x(qx + 1.8), self.y(qy + qs - 1.8), (qs - 3.6) * U, (qs - 3.6) * U)
        self.text(qx + qs / 2, qy + qs + 4, "Scannez-moi", 2.8, "Helvetica-Bold", self.role, center=True)
        self.dash(qx + qs / 2, qy + qs + 5.4, centered=True)


def card_pdf(card):
    """PDF de la carte : 2 pages (recto, verso) ; 1 page (verso) pour le style « Pagne verso »."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(PAGE_W, PAGE_H))
    c.setTitle(f"Carte de visite — {card.full_name}")
    c.setAuthor(settings.PLATFORM_NAME)
    pal = PALETTES.get(card.theme, PALETTES["green"])
    painter = _Painter(c, pal)
    wax = card.layout in (BusinessCard.Layout.WAX, BusinessCard.Layout.WAXTOP)
    if card.layout != BusinessCard.Layout.WAXTOP:
        (painter.front_wax if wax else painter.front_plain)(card)
        c.showPage()
    painter.back(card, pattern=wax)
    c.showPage()
    c.save()
    return buf.getvalue()
