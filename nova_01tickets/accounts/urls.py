from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.NovaLoginView.as_view(), name="login"),
    path("deconnexion/", LogoutView.as_view(), name="logout"),
    path("inscription/<str:role>/", views.register, name="register"),
    path("profil/", views.profile, name="profile"),
]
