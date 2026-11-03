from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("evenements/<int:pk>/", views.detail, name="detail"),
    path("organisateur/", views.orga_dashboard, name="orga_dashboard"),
    path("organisateur/evenements/nouveau/", views.event_create, name="create"),
    path("organisateur/evenements/<int:pk>/modifier/", views.event_edit, name="edit"),
    path("organisateur/evenements/<int:pk>/publier/", views.event_toggle, name="toggle"),
    path("organisateur/retraits/", views.withdraw, name="withdraw"),
]
