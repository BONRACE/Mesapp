from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("tableau-de-bord/", views.dashboard_redirect, name="dashboard_redirect"),
    path("mes-billets/", views.spectateur_dashboard, name="spectateur_dashboard"),
    path("organisateur/", views.organizer_dashboard, name="organizer_dashboard"),
    path("organisateur/retrait/", views.withdraw, name="withdraw"),
]
