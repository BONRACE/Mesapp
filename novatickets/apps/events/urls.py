from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.liste_publique, name="liste"),
    path("organisateur/", views.dashboard, name="dashboard_organisateur"),
    path("organisateur/mes-evenements/", views.mes_evenements, name="mes_evenements"),
    path("organisateur/nouveau/", views.creer, name="creer"),
    path("organisateur/<int:pk>/modifier/", views.modifier, name="modifier"),
    path("organisateur/<int:pk>/publier/", views.publier, name="publier"),
    path("<slug:slug>/", views.detail, name="detail"),
]
