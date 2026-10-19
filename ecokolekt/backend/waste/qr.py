"""QR codes sécurisés : jeton signé HMAC-SHA256, lié à une demande, à usage unique.

Format : EK1.<pickup_id_hex>.<nonce>.<signature>
 - la signature empêche de forger un QR ;
 - le nonce est stocké en base et régénéré à l'usage : un QR scanné (ou photographié) ne sert qu'une fois ;
 - le serveur vérifie en plus que le collecteur est assigné et proche du ménage (voir services.complete_pickup).
"""
import base64
import hashlib
import hmac
import io
import uuid

import qrcode
from django.conf import settings
from qrcode.constants import ERROR_CORRECT_M

PREFIX = "EK1"


class InvalidToken(Exception):
    pass


def _sig(payload: str) -> str:
    mac = hmac.new(settings.QR_SIGNING_KEY.encode(), payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac[:16]).decode().rstrip("=")


def make_token(pickup) -> str:
    payload = f"{PREFIX}.{pickup.id.hex}.{pickup.qr_nonce}"
    return f"{payload}.{_sig(payload)}"


def parse_token(token: str):
    parts = (token or "").strip().split(".")
    if len(parts) != 4 or parts[0] != PREFIX:
        raise InvalidToken("QR code non reconnu.")
    payload = ".".join(parts[:3])
    if not hmac.compare_digest(parts[3], _sig(payload)):
        raise InvalidToken("QR code falsifié.")
    try:
        return uuid.UUID(hex=parts[1]), parts[2]
    except ValueError:
        raise InvalidToken("QR code non reconnu.")


def render_png(token: str) -> bytes:
    img = qrcode.make(token, error_correction=ERROR_CORRECT_M, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
