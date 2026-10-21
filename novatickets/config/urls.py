from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("compte/", include("accounts.urls")),
    path("evenements/", include("events.urls")),
    path("billets/", include("tickets.urls")),
    path("paiement/", include("payments.urls")),
    path("cartes/", include("cards.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "core.views.error_404"
handler403 = "core.views.error_403"
