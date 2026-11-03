from decimal import Decimal

from django.conf import settings

from .countries import COUNTRIES


def commission_label():
    """2.5 -> « 2,5 » (virgule française) ; 5 -> « 5 »."""
    return f"{Decimal(str(settings.PLATFORM_COMMISSION_PERCENT)):g}".replace(".", ",")


def site(request):
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "COMMISSION": commission_label(),
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "CURRENCY": settings.CURRENCY,
        "COUNTRIES": COUNTRIES,
    }
