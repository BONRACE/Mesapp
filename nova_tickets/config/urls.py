from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from events import views as event_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/", include("accounts.urls")),
    path("evenements/", include("events.urls")),
    path("", include("orders.urls")),
    path("", include("core.urls")),
    path("scanner/", event_views.scanner_view, name="scanner"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
