from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("sites/", views.site_list, name="site_list"),
    path("sites/nouveau/", views.site_create, name="site_create"),
    path("enlevements/nouveau/", views.pickup_create, name="pickup_create"),
    path("collecte/disponibles/", views.available_pickups, name="available_pickups"),
    path("collecte/<int:pk>/accepter/", views.accept_pickup, name="accept_pickup"),
    path("tournees/planifier/", views.plan_route, name="plan_route"),
    path("tournees/<int:pk>/", views.route_detail, name="route_detail"),
    path("tournees/<int:pk>/recalculer/", views.route_replan, name="route_replan"),
    path("enlevements/<int:pk>/collecte/", views.stop_collected, name="stop_collected"),
]
