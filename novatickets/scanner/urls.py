from django.urls import path

from . import views

app_name = "scanner"

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:event_id>/", views.scan_page, name="scan"),
    path("<int:event_id>/verifier/", views.scan_api, name="api"),
]
