from django.conf import settings

from .countries import COUNTRIES


def site(request):
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "COMMISSION": settings.PLATFORM_COMMISSION_PERCENT,
        "CURRENCY": settings.CURRENCY,
        "COUNTRIES": COUNTRIES,
    }
