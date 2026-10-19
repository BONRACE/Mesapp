"""Les 5 modèles de cartes de visite. Chaque modèle fournit un recto (identité) et un verso (contacts + QR)."""
import math

from PIL import Image

from .cardkit import (H, W, Cv, draw_rows, fit_line, fit_name, kraft_paper, lum, medallion, mix, rgba, vcard_text,
                      vgradient, wrap)

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def _pitch(rows, start, bottom, top=56):
    n = max(1, len(rows))
    avail = bottom - start - (34 if any(k == "pin" for k, _ in rows) else 0)
    return max(36, min(top, avail / n))


def _name_block(cv, c, x, y, key, max_size, min_size, max_w, fill, lh=1.08):
    lines, size = fit_name(cv, c.name or "Votre nom", key, max_size, min_size, max_w)
    for i, ln in enumerate(lines):
        cv.text(x, y + i * size * lh, ln, key, size, fill)
    return y + (len(lines) - 1) * size * lh, size


# =============================================================== 1. ATELIER (kraft + tampon)
KRAFT = (201, 166, 120)
BROWN = (52, 34, 22)


def _kraft(s):
    return Cv(s, kraft_paper(round(W * s), round(H * s), KRAFT))


def _ink(c):
    return mix(c.accent, (38, 26, 18), 0.6)


def atelier_recto(c, s):
    cv, ink = _kraft(s), _ink(c)
    m = 30
    for k, (x0, y0, x1, y1) in enumerate([(m, m, W - m, m), (W - m, m, W - m, H - m),
                                           (W - m, H - m, m, H - m), (m, H - m, m, m)]):
        cv.hand_line(x0, y0, x1, y1, rgba(BROWN, .78), 2.4, 1.0, seed=c.seed + k)
    cv.rect((42, 42, W - 42, H - 42), outline=rgba(BROWN, .32), w=1)

    cx, cy, R = 525, 262, 178
    snap = cv.snapshot((cx - R - 10, cy - R - 10, cx + R + 10, cy + R + 10))
    cv.circle(cx, cy, R, outline=ink, w=6)
    cv.circle(cx, cy, R - 14, outline=ink, w=2)
    cv.circle(cx, cy, 112, outline=ink, w=2.5)
    rt = 132
    span = rt * math.radians(168)
    top, ts = fit_line(cv, (c.company or "Votre entreprise").upper(), "pop_semi", 30, 17, span, 4)
    cv.arc_text(cx, cy, rt, top, "pop_semi", ts, ink, False, 4)
    place = (c.place or "Fait main").upper()
    bot, bs = fit_line(cv, place, "pop_semi", 24, 15, span, 5)
    cv.arc_text(cx, cy, rt + bs * 0.72, bot, "pop_semi", bs, ink, True, 5)
    cv.star(cx - 144, cy, 9, ink)
    cv.star(cx + 144, cy, 9, ink)
    if c.logo is not None:
        cv.paste_fit(c.logo, cx, cy, 150, 150)
    else:
        cv.text(cx, cy + 32, c.initials, "play", 92 if len(c.initials) < 2 else 80, ink, "m")
        cv.hand_line(cx - 42, cy + 58, cx + 42, cy + 58, ink, 3, 1.0, seed=c.seed)
    cv.erode(snap, c.seed, 1.4)

    if c.tagline.strip():
        txt, size = fit_line(cv, c.tagline.strip(), "script", 46, 26, 780)
        cv.hand_line(300, 482, 478, 482, rgba(BROWN, .7), 2, 1.0, seed=c.seed + 9)
        cv.hand_line(572, 482, 750, 482, rgba(BROWN, .7), 2, 1.0, seed=c.seed + 10)
        cv.star(cx, 482, 7, ink)
        cv.text(cx, 530, txt, "script", size, BROWN, "m")
    return cv.img


def atelier_verso(c, s):
    cv, ink = _kraft(s), _ink(c)
    m = 30
    for k, (x0, y0, x1, y1) in enumerate([(m, m, W - m, m), (W - m, m, W - m, H - m),
                                           (W - m, H - m, m, H - m), (m, H - m, m, m)]):
        cv.hand_line(x0, y0, x1, y1, rgba(BROWN, .78), 2.4, 1.0, seed=c.seed + 20 + k)
    cv.rect((42, 42, W - 42, H - 42), outline=rgba(BROWN, .32), w=1)

    y, size = _name_block(cv, c, 78, 150, "play", 58, 36, 630, BROWN)
    if c.title.strip():
        t, ts = fit_line(cv, c.title.strip(), "script", 40, 26, 620)
        cv.text(78, y + 46, t, "script", ts, ink)
        y += 46
    cv.hand_line(78, y + 26, 330, y + 26, rgba(BROWN, .7), 2.4, 1.2, seed=c.seed + 31)
    rows = c.rows()
    start = y + 76
    draw_rows(cv, rows, 70, start, _pitch(rows, start, 535), 26, "pop_med", BROWN, ink, 640)

    # étiquette crème avec le QR
    lx0, ly0, lx1, ly1 = 742, 108, 972, 338
    cv.rect((lx0 + 4, ly0 + 6, lx1 + 4, ly1 + 6), fill=rgba(BLACK, .16), r=10)
    cv.rect((lx0, ly0, lx1, ly1), fill=(247, 238, 217), r=10)
    cv.rect((lx0 + 8, ly0 + 8, lx1 - 8, ly1 - 8), outline=rgba(BROWN, .4), w=1.2, r=6)
    cv.qr(857, 223, 218, vcard_text(c), BROWN, (247, 238, 217), 22)
    cv.text(857, 392, "Scannez-moi", "script", 44, BROWN, "m")
    cv.text(857, 428, "et enregistrez mon contact", "pop", 17, rgba(BROWN, .85), "m")
    cv.star(857, 462, 8, ink)
    return cv.img


# =============================================================== 2. ÉPURE (blanc, minimal)
PAPER = (252, 252, 250)


def epure_recto(c, s):
    a = c.accent
    cv = Cv(s, PAPER)
    cv.circle(W, H, 270, fill=a)
    cv.circle(W, H, 190, fill=mix(a, WHITE, .18))
    cv.circle(W, H, 112, fill=mix(a, BLACK, .12))
    cv.rect((0, 0, 18, H), fill=a)
    if c.logo is not None:
        cv.paste_fit(c.logo, 138, 128, 150, 100)
    else:
        medallion(cv, 130, 125, 52, c, a, None, WHITE)
    lines, size = fit_name(cv, c.company or "Votre entreprise", "pop_semi", 76, 40, 640)
    y = 330
    for i, ln in enumerate(lines):
        cv.text(80, y + i * size * 1.1, ln, "pop_semi", size, (22, 30, 38))
    y += (len(lines) - 1) * size * 1.1
    cv.rect((80, y + 36, 150, y + 42), fill=a, r=3)
    if c.tagline.strip():
        for i, ln in enumerate(wrap(cv, c.tagline.strip(), "pop", 28, 560)[:2]):
            cv.text(80, y + 90 + i * 38, ln, "pop", 28, (100, 112, 125))
    return cv.img


def epure_verso(c, s):
    a = c.accent
    cv = Cv(s, PAPER)
    cv.rect((0, 0, 18, H), fill=a)
    y, size = _name_block(cv, c, 80, 135, "pop_semi", 54, 34, 600, (22, 30, 38))
    if c.title.strip():
        t = c.title.strip().upper()
        cv.text(80, y + 42, t if cv.tw(t, "pop_semi", 22, 3) < 600 else c.title.strip(), "pop_semi", 22, a, track=3)
        y += 42
    cv.rect((80, y + 28, 150, y + 33), fill=a, r=2)
    rows = c.rows()
    start = y + 86
    draw_rows(cv, rows, 70, start, _pitch(rows, start, 548, 54), 26, "pop", (45, 55, 66), a, 640,
              sep=(226, 230, 232))
    cv.qr(850, 270, 236, vcard_text(c), mix(a, BLACK, .55), PAPER, 14)
    cv.text(850, 420, "Enregistrer le contact", "pop_med", 20, (100, 112, 125), "m")
    cv.circle(850, 462, 5, fill=a)
    return cv.img


# =============================================================== 3. PRESTIGE (nuit & métal)
def _metal(c):
    a = c.accent
    return mix(a, WHITE, .55 if lum(a) < .3 else .28)


def _ornament(cv, x0, x1, y, col, w=1.6):
    cx = (x0 + x1) / 2
    cv.line([(x0, y), (cx - 16, y)], col, w)
    cv.line([(cx + 16, y), (x1, y)], col, w)
    cv.diamond(cx, y, 6, col)


def _frame(cv, col):
    for m, w in ((30, 2.2), (42, 1)):
        cv.rect((m, m, W - m, H - m), outline=col, w=w)
    for x, y in ((30, 30), (W - 30, 30), (30, H - 30), (W - 30, H - 30)):
        cv.diamond(x, y, 9, col)


def _night(s):
    return Cv(s, vgradient(round(W * s), round(H * s), (24, 29, 36), (9, 11, 15)))


def prestige_recto(c, s):
    cv, mt = _night(s), _metal(c)
    _frame(cv, mt)
    if c.logo is not None:
        cv.circle(525, 150, 62, fill=(245, 240, 228))
        cv.paste_fit(c.logo, 525, 150, 84, 84)
        cv.circle(525, 150, 62, outline=mt, w=2.5)
    else:
        cv.circle(525, 150, 56, outline=mt, w=2.5)
        cv.circle(525, 150, 48, outline=rgba(mt, .45), w=1)
        cv.text(525, 150 + 17, c.initials, "play", 52 if len(c.initials) < 2 else 44, mt, "m")
    name, size = fit_line(cv, (c.company or "Votre entreprise").upper(), "corm", 66, 34, 800, 8)
    cv.text(525, 318, name, "corm", size, (244, 240, 230), "m", track=8)
    _ornament(cv, 285, 765, 356, mt)
    if c.tagline.strip():
        t, ts = fit_line(cv, c.tagline.strip(), "corm_it", 34, 22, 760)
        cv.text(525, 412, t, "corm_it", ts, mt, "m")
    if c.place:
        cv.text(525, 520, c.place.upper(), "pop_med", 15, rgba(mt, .8), "m", track=6)
    return cv.img


def prestige_verso(c, s):
    cv, mt = _night(s), _metal(c)
    _frame(cv, mt)
    y, size = _name_block(cv, c, 84, 168, "corm", 66, 38, 600, (244, 240, 230))
    if c.title.strip():
        t, ts = fit_line(cv, c.title.strip().upper(), "pop_med", 20, 14, 600, 5)
        cv.text(84, y + 44, t, "pop_med", ts, mt, track=5)
        y += 44
    cv.line([(84, y + 30), (250, y + 30)], mt, 2)
    cv.diamond(262, y + 30, 5, mt)
    rows = c.rows()
    start = y + 88
    draw_rows(cv, rows, 76, start, _pitch(rows, start, 536, 52), 25, "pop", (226, 224, 218), mt, 620)
    cv.rect((742, 128, 972, 358), fill=(246, 240, 226), r=6)
    cv.rect((750, 136, 964, 350), outline=mt, w=1.5, r=3)
    cv.qr(857, 243, 214, vcard_text(c), (20, 24, 30), (246, 240, 226), 20)
    cv.text(857, 408, "SCANNEZ-MOI", "pop_med", 16, mt, "m", track=5)
    cv.diamond(857, 440, 6, mt)
    return cv.img


# =============================================================== 4. WAX (motifs africains)
WARM = (244, 185, 66)
T = 75


def _wax(cv, x0, y0, cols, rows_, a):
    dark, light = mix(a, BLACK, .45), mix(a, WHITE, .72)
    cv.rect((x0, y0, x0 + cols * T, y0 + rows_ * T), fill=a)
    for i in range(cols):
        for j in range(rows_):
            cx, cy = x0 + i * T + T / 2, y0 + j * T + T / 2
            if (i + j) % 2 == 0:
                cv.circle(cx, cy, 31, fill=WARM)
                cv.circle(cx, cy, 24, fill=dark)
                cv.circle(cx, cy, 16, fill=light)
                cv.circle(cx, cy, 8, fill=a)
            else:
                cv.diamond(cx, cy, 31, dark)
                cv.diamond(cx, cy, 22, light)
                cv.diamond(cx, cy, 13, WARM)
                cv.circle(cx, cy, 4, fill=dark)
            cv.circle(cx + T / 2, cy + T / 2, 3, fill=light)


def _zigzag_v(cv, x, a, col):
    for k in range(0, H, 30):
        cv.poly([(x, k), (x + 14, k + 15), (x, k + 30)], col)


def wax_recto(c, s):
    a, cream = c.accent, (251, 245, 233)
    cv = Cv(s, cream)
    _wax(cv, 0, 0, 4, 8, a)
    cv.rect((300, 0, 312, H), fill=mix(a, BLACK, .45))
    _zigzag_v(cv, 312, a, WARM)
    x = 372
    if c.logo is not None:
        cv.paste_fit(c.logo, x + 60, 120, 140, 100)
    else:
        medallion(cv, x + 52, 118, 52, c, a, WARM, WHITE, ring_w=5)
    lines, size = fit_name(cv, c.company or "Votre entreprise", "pop_bold", 62, 34, 620)
    y = 282
    for i, ln in enumerate(lines):
        cv.text(x, y + i * size * 1.1, ln, "pop_bold", size, (46, 28, 18))
    y += (len(lines) - 1) * size * 1.1
    cv.rect((x, y + 30, x + 90, y + 38), fill=WARM, r=4)
    cv.rect((x + 100, y + 30, x + 130, y + 38), fill=a, r=4)
    if c.tagline.strip():
        for i, ln in enumerate(wrap(cv, c.tagline.strip(), "pop_med", 26, 600)[:2]):
            cv.text(x, y + 84 + i * 36, ln, "pop_med", 26, mix(a, BLACK, .5))
    return cv.img


def wax_verso(c, s):
    a, cream = c.accent, (251, 245, 233)
    cv = Cv(s, cream)
    _wax(cv, 0, 0, 14, 1, a)
    cv.rect((0, T, W, T + 8), fill=mix(a, BLACK, .45))
    y, size = _name_block(cv, c, 70, 192, "pop_bold", 50, 32, 620, (46, 28, 18))
    if c.title.strip():
        t, ts = fit_line(cv, c.title.strip(), "pop_med", 26, 18, 620)
        cv.text(70, y + 40, t, "pop_med", ts, mix(a, BLACK, .15))
        y += 40
    rows = c.rows()
    start = y + 72
    draw_rows(cv, rows, 62, start, _pitch(rows, start, 566, 50), 25, "pop_med", (60, 40, 28), a, 640)
    cv.rect((748, 188, 978, 418), fill=WHITE, r=14)
    cv.rect((748, 188, 978, 418), outline=a, w=5, r=14)
    cv.qr(863, 303, 216, vcard_text(c), mix(a, BLACK, .5), WHITE, 18)
    cv.text(863, 462, "Scannez-moi", "pop_semi", 22, mix(a, BLACK, .4), "m")
    cv.rect((833, 478, 893, 485), fill=WARM, r=3)
    return cv.img


# =============================================================== 5. AURORE (bloc de couleur)
def _glow(cv, a):
    cv.circle(W - 40, 80, 250, fill=rgba(WHITE, .07))
    cv.circle(W - 40, 80, 170, fill=rgba(WHITE, .07))
    cv.circle(60, H + 40, 220, fill=rgba(BLACK, .08))


def _color_bg(s, a):
    return vgradient(round(W * s), round(H * s), mix(a, WHITE, .12), mix(a, BLACK, .3))


def aurore_recto(c, s):
    a = c.accent
    cv = Cv(s, _color_bg(s, a))
    _glow(cv, a)
    if c.logo is not None:
        cv.circle(130, 128, 62, fill=WHITE)
        cv.paste_fit(c.logo, 130, 128, 84, 84)
    else:
        cv.circle(130, 128, 62, fill=WHITE)
        cv.text(130, 128 + 22, c.initials, "pop_bold", 62 if len(c.initials) < 2 else 50, mix(a, BLACK, .2), "m")
    lines, size = fit_name(cv, c.company or "Votre entreprise", "pop_bold", 74, 38, 760)
    y = 340
    for i, ln in enumerate(lines):
        cv.text(80, y + i * size * 1.08, ln, "pop_bold", size, WHITE)
    y += (len(lines) - 1) * size * 1.08
    cv.rect((80, y + 34, 160, y + 41), fill=WHITE, r=3)
    if c.tagline.strip():
        for i, ln in enumerate(wrap(cv, c.tagline.strip(), "pop", 28, 720)[:2]):
            cv.text(80, y + 90 + i * 38, ln, "pop", 28, rgba(WHITE, .88))
    if c.place:
        cv.text(80, 556, c.place.upper(), "pop_med", 16, rgba(WHITE, .75), track=5)
    return cv.img


def aurore_verso(c, s):
    a = c.accent
    cv = Cv(s, (255, 255, 255))
    bx = 668
    cv.img.paste(_color_bg(s, a).crop((round(bx * s), 0, cv.pw, cv.ph)), (round(bx * s), 0))
    cv.circle(W - 20, 40, 200, fill=rgba(WHITE, .07))
    cv.circle(W - 20, 40, 130, fill=rgba(WHITE, .07))
    cv.rect((bx, 0, bx + 8, H), fill=rgba(WHITE, .35))
    y, size = _name_block(cv, c, 64, 142, "pop_bold", 52, 32, 560, (22, 30, 38))
    if c.title.strip():
        t, ts = fit_line(cv, c.title.strip(), "pop_med", 26, 18, 560)
        cv.text(64, y + 42, t, "pop_med", ts, a)
        y += 42
    rows = c.rows()
    start = y + 82
    draw_rows(cv, rows, 56, start, _pitch(rows, start, 566, 52), 24, "pop", (45, 55, 66), a, 590, sep=(228, 232, 235))
    qx = (bx + 8 + W) / 2
    cv.rect((qx - 125 + 3, 168 + 6, qx + 125 + 3, 418 + 6), fill=rgba(BLACK, .18), r=22)
    cv.rect((qx - 125, 168, qx + 125, 418), fill=WHITE, r=22)
    cv.qr(qx, 293, 236, vcard_text(c), mix(a, BLACK, .5), WHITE, 16)
    cv.text(qx, 470, "Scannez pour", "pop", 20, rgba(WHITE, .9), "m")
    cv.text(qx, 498, "enregistrer le contact", "pop_semi", 20, WHITE, "m")
    return cv.img


# =============================================================== registre
TEMPLATES = {
    "atelier": {"label": "Atelier", "hint": "Kraft & tampon artisanal", "recto": atelier_recto, "verso": atelier_verso},
    "epure": {"label": "Épuré", "hint": "Blanc, net et moderne", "recto": epure_recto, "verso": epure_verso},
    "prestige": {"label": "Prestige", "hint": "Nuit & finitions métal", "recto": prestige_recto, "verso": prestige_verso},
    "wax": {"label": "Wax", "hint": "Motifs africains colorés", "recto": wax_recto, "verso": wax_verso},
    "aurore": {"label": "Aurore", "hint": "Grand bloc de couleur", "recto": aurore_recto, "verso": aurore_verso},
}
TEMPLATE_CHOICES = [(k, v["label"]) for k, v in TEMPLATES.items()]
