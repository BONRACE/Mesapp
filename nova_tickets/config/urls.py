from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("compte/", include("accounts.urls")),
    path("", include("events.urls")),
    path("", include("orders.urls")),
    path("paiement/", include("payments.urls")),
    path("organisateur/scanner/", include("scanner.urls")),
    path("organisateur/analytiques/", include("analytics.urls")),
    path("organisateur/moyens-retrait/", include("payouts.urls")),
    path("organisateur/abonnement/", include("subscriptions.urls")),
    path("carte/", include("cards.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
