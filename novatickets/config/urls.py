"""Routage racine de NovaTickets."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("comptes/", include("apps.accounts.urls")),
    path("evenements/", include("apps.events.urls")),
    path("billets/", include("apps.tickets.urls")),
    path("paiements/", include("apps.payments.urls")),
    path("cartes-de-visite/", include("apps.cards.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
