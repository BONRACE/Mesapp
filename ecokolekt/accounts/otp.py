"""Logique OTP : émission limitée, stockage haché, vérification à temps constant."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import OTPCode
from .sms import get_sms_backend


def _hash_code(phone_number, code):
    payload = f"{phone_number}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()


def _generate_code():
    return f"{secrets.randbelow(10**6):06d}"


def _sends_last_hour(phone_number):
    since = timezone.now() - timedelta(hours=1)
    return OTPCode.objects.filter(phone_number=phone_number, created_at__gte=since).count()


def issue_otp(phone_number):
    """Crée un code et l'envoie. Retourne False si la limite d'envoi est atteinte."""
    if _sends_last_hour(phone_number) >= settings.OTP_MAX_SENDS_PER_HOUR:
        return False
    code = _generate_code()
    OTPCode.objects.create(
        phone_number=phone_number,
        code_hash=_hash_code(phone_number, code),
        expires_at=timezone.now() + timedelta(seconds=settings.OTP_TTL_SECONDS),
    )
    get_sms_backend().send(phone_number, f"EcoKolekt : votre code est {code}. Valable 5 minutes.")
    return True


def verify_otp(phone_number, code):
    """Vérifie le code le plus récent encore valable. Un seul usage, nombre d'essais borné."""
    otp = (
        OTPCode.objects.filter(phone_number=phone_number, consumed=False, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .first()
    )
    if otp is None or otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        return False
    otp.attempts += 1
    otp.save(update_fields=["attempts"])
    if not hmac.compare_digest(otp.code_hash, _hash_code(phone_number, code)):
        return False
    otp.consumed = True
    otp.save(update_fields=["consumed"])
    return True
