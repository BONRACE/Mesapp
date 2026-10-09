from django.urls import path

from . import views

app_name = "events"

urlpatterns = [
    path("nouveau/", views.create, name="create"),
    path("<int:pk>/modifier/", views.edit, name="edit"),
    path("<int:pk>/publier/", views.toggle_publish, name="toggle_publish"),
    path("<int:pk>/supprimer/", views.delete, name="delete"),
    path("<slug:slug>/", views.detail, name="detail"),
]
