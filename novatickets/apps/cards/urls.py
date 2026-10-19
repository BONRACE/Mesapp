from django.urls import path

from . import views

app_name = "cards"

urlpatterns = [
    path("", views.liste, name="liste"),
    path("nouvelle/", views.creer, name="creer"),
    path("<int:pk>/paiement/", views.paiement, name="paiement"),
    path("<int:pk>/telecharger/", views.telecharger, name="telecharger"),
    path("<int:pk>/supprimer/", views.supprimer, name="supprimer"),
]
