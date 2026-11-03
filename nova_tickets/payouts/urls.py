from django.urls import path

from . import views

app_name = "payouts"

urlpatterns = [
    path("", views.method_list, name="list"),
    path("nouveau/", views.method_create, name="create"),
    path("<int:pk>/modifier/", views.method_edit, name="edit"),
    path("<int:pk>/defaut/", views.method_default, name="default"),
    path("<int:pk>/supprimer/", views.method_delete, name="delete"),
]
