from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.listing_list, name="list"),
    path("offre/nouvelle/", views.listing_create, name="create"),
    path("mes-offres/", views.my_listings, name="mine"),
    path("offre/<int:pk>/", views.listing_detail, name="detail"),
    path("offre/<int:pk>/basculer/", views.listing_toggle, name="toggle"),
    path("offre/<int:pk>/commander/", views.order_create, name="order"),
    path("commandes/", views.order_list, name="orders"),
    path("commandes/<int:pk>/annuler/", views.order_cancel, name="order_cancel"),
]
