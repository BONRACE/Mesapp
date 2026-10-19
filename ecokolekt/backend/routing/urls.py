from django.urls import path

from . import views

urlpatterns = [
    path("route/", views.MyRouteView.as_view()),
    path("collectors/live/", views.LiveCollectorsView.as_view()),
]
