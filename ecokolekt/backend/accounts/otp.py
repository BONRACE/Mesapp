"""Émission et vérification des OTP + envoi SMS."""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OTPCode

log = logging.getLogger(__name__)


class OTPError(Exception):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


def _hash(phone: str, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def issue_otp(phone: str) -> str:
    now = timezone.now()
    last = OTPCode.objects.filter(phone=phone).order_by("-created_at").first()
    if last:
        elapsed = (now - last.created_at).total_seconds()
        if elapsed < settings.OTP_RESEND_SECONDS:
            raise OTPError("Patientez un instant avant de redemander un code.", int(settings.OTP_RESEND_SECONDS - elapsed))
    recent = OTPCode.objects.filter(phone=phone, created_at__gte=now - timedelta(hours=1)).count()
    if recent >= settings.OTP_MAX_PER_HOUR:
        raise OTPError("Trop de demandes. Réessayez dans une heure.", 3600)
    code = f"{secrets.randbelow(10**6):06d}"
    OTPCode.objects.create(
        phone=phone, code_hash=_hash(phone, code), expires_at=now + timedelta(seconds=settings.OTP_TTL_SECONDS)
    )
    return code


def verify_otp(phone: str, code: str) -> None:
    """Lève OTPError si le code est invalide. Le compteur d'essais est persisté même en cas d'échec."""
    error = None
    with transaction.atomic():
        otp = (
            OTPCode.objects.select_for_update()
            .filter(phone=phone, consumed_at__isnull=True, expires_at__gt=timezone.now())
            .order_by("-created_at")
            .first()
        )
        if not otp:
            error = "Code expiré. Demandez-en un nouveau."
        elif otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            error = "Trop d'essais. Demandez un nouveau code."
        else:
            otp.attempts += 1
            if hmac.compare_digest(otp.code_hash, _hash(phone, code)):
                otp.consumed_at = timezone.now()
            else:
                error = "Code incorrect."
            otp.save(update_fields=["attempts", "consumed_at"])
    if error:
        raise OTPError(error)


def send_sms(phone: str, message: str) -> None:
    if settings.SMS_BACKEND == "http":
        # Adaptez le payload à votre agrégateur SMS (Twilio, Infobip, Orange, etc.)
        resp = requests.post(
            settings.SMS_HTTP_URL,
            headers={"Authorization": f"Bearer {settings.SMS_HTTP_TOKEN}"},
            json={"to": phone, "from": settings.SMS_SENDER, "text": message},
            timeout=10,
        )
        resp.raise_for_status()
    else:
        log.warning("[SMS console] %s -> %s", phone, message)
