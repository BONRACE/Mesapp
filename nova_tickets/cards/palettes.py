"""Palettes des cartes de visite : une seule source pour le motif « pagne » (SVG), le CSS et la couleur du QR code.

base = aplat dominant · dark = traits foncés et texte · tint = cercles clairs · accent = touches jaunes · paper = fond « crème ».
La palette « sunset » reprend exactement les couleurs de la carte de référence (orange, brun, jaune, crème).
"""
PALETTES = {
    "sunset":   dict(base="#ea5406", dark="#7e3006", tint="#f6ccba", accent="#f0b442", paper="#fbf4e9", ink="#2b1608"),
    "green":    dict(base="#16a34a", dark="#14532d", tint="#d1fae5", accent="#fde047", paper="#f4faf3", ink="#0f2a17"),
    "forest":   dict(base="#166534", dark="#052e16", tint="#bbf7d0", accent="#facc15", paper="#f3f8f4", ink="#052e16"),
    "mint":     dict(base="#10b981", dark="#065f46", tint="#d1fae5", accent="#fcd34d", paper="#f2fbf7", ink="#064e3b"),
    "ocean":    dict(base="#0284c7", dark="#0c4a6e", tint="#bae6fd", accent="#fbbf24", paper="#f1f8fc", ink="#0c2d48"),
    "navy":     dict(base="#1d5a96", dark="#0f3a66", tint="#cfe0f3", accent="#f28c28", paper="#f3f6fa", ink="#0f2744"),
    "violet":   dict(base="#7c3aed", dark="#4c1d95", tint="#ddd6fe", accent="#fbbf24", paper="#f7f5fd", ink="#2e1065"),
    "rose":     dict(base="#e11d48", dark="#881337", tint="#fecdd3", accent="#fbbf24", paper="#fdf4f5", ink="#4c0519"),
    "gold":     dict(base="#d97706", dark="#713f12", tint="#fde68a", accent="#fde047", paper="#fffaf0", ink="#3a1f06"),
    "graphite": dict(base="#374151", dark="#111827", tint="#e5e7eb", accent="#f0b442", paper="#f6f6f6", ink="#111827"),
}


def rgb(theme, key="dark"):
    """Couleur d'une palette en tuple (r, g, b) — pour le QR code."""
    h = PALETTES.get(theme, PALETTES["green"])[key].lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
