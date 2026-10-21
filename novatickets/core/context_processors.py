from django.conf import settings


def platform(request):
    return {
        "PLATFORM_NAME": settings.PLATFORM_NAME,
        "CURRENCY": settings.CURRENCY,
        "BUSINESS_CARD_PRICE": settings.BUSINESS_CARD_PRICE,
        "MIN_WITHDRAWAL": settings.MIN_WITHDRAWAL,
    }
