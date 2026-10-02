from django.urls import path
from . import views

app_name = "events"

urlpatterns = [
    path("", views.catalogue, name="catalogue"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/acheter/<int:type_id>/", views.acheter_billet, name="acheter"),
    path("organisateur/tableau-de-bord/", views.organisateur_dashboard, name="organisateur_dashboard"),
    path("organisateur/creer/", views.event_create, name="event_create"),
    path("organisateur/<uuid:pk>/gerer/", views.event_manage, name="event_manage"),
]
