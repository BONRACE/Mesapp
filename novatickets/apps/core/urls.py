from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("a-propos/", views.a_propos, name="a_propos"),
    path("tableau-de-bord/", views.redirection_tableau_de_bord, name="redirection_tableau_de_bord"),
]
