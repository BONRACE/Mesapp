"""QR codes stylisés (modules arrondis, vert NovaTickets, logo au centre)."""
import io
from functools import lru_cache

import qrcode
from django.conf import settings
from PIL import Image
from qrcode.constants import ERROR_CORRECT_H
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers import RoundedModuleDrawer

GREEN = (21, 128, 61)
LOGO_MARK = settings.BASE_DIR / "static" / "img" / "logo-mark.png"


@lru_cache(maxsize=256)
def qr_png(data: str, box_size: int = 10, with_logo: bool = True) -> bytes:
    """PNG d'un QR code pour `data` (mis en cache : les URLs de ticket ne changent pas)."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    kwargs = {}
    if with_logo and LOGO_MARK.exists():
        kwargs["embeded_image_path"] = str(LOGO_MARK)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=SolidFillColorMask(back_color=(255, 255, 255), front_color=GREEN),
        **kwargs,
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def qr_image(data: str, box_size: int = 10, with_logo: bool = True) -> Image.Image:
    return Image.open(io.BytesIO(qr_png(data, box_size, with_logo))).convert("RGB")


def ticket_url(ticket) -> str:
    """URL absolue de vérification encodée dans le QR code du ticket."""
    return settings.SITE_URL.rstrip("/") + ticket.verify_path
