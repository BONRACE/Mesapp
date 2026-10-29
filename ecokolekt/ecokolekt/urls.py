from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("compte/", include("accounts.urls")),
    path("operations/", include("operations.urls")),
    path("tracabilite/", include("traceability.urls")),
    path("marche/", include("marketplace.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
