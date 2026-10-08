from django.conf import settings


def platform(request):
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "COMMISSION_PERCENT": int(settings.PLATFORM_COMMISSION_RATE * 100),
    }
