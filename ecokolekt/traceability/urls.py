from django.urls import path

from . import views

app_name = "traceability"

urlpatterns = [
    path("", views.batch_list, name="list"),
    path("<uuid:pk>/", views.batch_detail, name="detail"),
    path("<uuid:pk>/qr.png", views.batch_qr, name="qr"),
    path("<uuid:pk>/evenement/", views.batch_event, name="event"),
    path("scan/<str:token>/", views.scan, name="scan"),
]
