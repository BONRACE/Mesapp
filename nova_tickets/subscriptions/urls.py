from django.urls import path

from . import views

app_name = "subscriptions"

urlpatterns = [
    path("", views.index, name="index"),
    path("payer/", views.pay, name="pay"),
]
