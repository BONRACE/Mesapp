from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("inscription/spectateur/", views.inscription_spectateur, name="inscription_spectateur"),
    path("inscription/organisateur/", views.inscription_organisateur, name="inscription_organisateur"),
    path("connexion/", views.connexion, name="login"),
    path("deconnexion/", views.deconnexion, name="logout"),
    path("profil/", views.profil, name="profil"),
]
