"""Génération de QR codes stylisés (SVG) avec segno — aucune dépendance image."""
import io

import segno


def qr_svg_data_uri(contenu, couleur="#065f46"):
    """Renvoie un data-URI SVG utilisable directement dans un <img>."""
    qr = segno.make(contenu, error="m")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=6, border=1, dark=couleur, light=None)
    import base64

    encode = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/svg+xml;base64,{encode}"
