from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.login_phone, name="login"),
    path("verification/", views.verify, name="verify"),
    path("renvoyer-code/", views.resend, name="resend"),
    path("bienvenue/", views.onboarding, name="onboarding"),
    path("deconnexion/", views.logout_view, name="logout"),
]
