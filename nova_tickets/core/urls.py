from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("tableau-de-bord/", views.dashboard_redirect, name="dashboard_redirect"),
    path("mes-billets/", views.spectateur_dashboard, name="spectateur_dashboard"),
    path("organisateur/", views.organizer_dashboard, name="organizer_dashboard"),
    path("organisateur/retrait/", views.withdraw, name="withdraw"),
    # Cartes de visite
    path("carte-de-visite/", views.card_list, name="card_list"),
    path("carte-de-visite/nouvelle/", views.card_create, name="card_create"),
    path("carte-de-visite/<int:pk>/", views.card_detail, name="card_detail"),
    path("carte-de-visite/<int:pk>/modifier/", views.card_edit, name="card_edit"),
    path("carte-de-visite/<int:pk>/supprimer/", views.card_delete, name="card_delete"),
    path("carte-de-visite/<int:pk>/carte.pdf", views.card_pdf, name="card_pdf"),
    path("carte-de-visite/<int:pk>/contact.vcf", views.card_vcf, name="card_vcf"),
    path("carte-de-visite/<int:pk>/<str:side>.png", views.card_image, name="card_image"),
]
