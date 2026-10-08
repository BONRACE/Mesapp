from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.NovaLoginView.as_view(), name="login"),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("inscription/", views.register_choice, name="register"),
    path("inscription/spectateur/", views.register_spectateur, name="register_spectateur"),
    path("inscription/organisateur/", views.register_organisateur, name="register_organisateur"),
    path("profil/", views.profile, name="profile"),
]
