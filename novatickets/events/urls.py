from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("", views.event_list, name="list"),
    path("organisateur/", views.dashboard, name="dashboard"),
    path("nouveau/", views.event_create, name="create"),
    path("<slug:slug>/", views.event_detail, name="detail"),
    path("<slug:slug>/gerer/", views.event_manage, name="manage"),
    path("<slug:slug>/modifier/", views.event_edit, name="edit"),
    path("<slug:slug>/publier/", views.event_toggle_publish, name="toggle_publish"),
    path("<slug:slug>/supprimer/", views.event_delete, name="delete"),
]
