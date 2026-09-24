from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("inscription/spectateur/", views.register_spectateur, name="register_spectateur"),
    path("inscription/organisateur/", views.register_organisateur, name="register_organisateur"),
    path("inscription/", views.register_choice, name="register_choice"),
    path("profil/", views.profile_edit, name="profile_edit"),
]
