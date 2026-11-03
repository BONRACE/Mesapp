from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("verification/<str:reference>/", views.verify, name="verify"),
    path("conditions-generales/", views.terms, name="terms"),
]
