from django.urls import path

from . import views

app_name = "cards"

urlpatterns = [
    path("", views.card_list, name="list"),
    path("nouvelle/", views.card_create, name="create"),
    path("apercu/", views.live_preview, name="live_preview"),
    path("modele/<str:theme>/<str:side>.png", views.theme_sample, name="theme_sample"),
    path("<int:pk>/", views.card_detail, name="detail"),
    path("<int:pk>/modifier/", views.card_edit, name="edit"),
    path("<int:pk>/payer/", views.card_pay, name="pay"),
    path("<int:pk>/supprimer/", views.card_delete, name="delete"),
    path("<int:pk>/apercu/<str:side>.png", views.saved_preview, name="saved_preview"),
    path("<int:pk>/telecharger/<str:fmt>/", views.download, name="download"),
]
