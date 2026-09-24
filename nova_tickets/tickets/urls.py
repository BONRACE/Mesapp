from django.urls import path
from . import views

app_name = "tickets"

urlpatterns = [
    path("mon-espace/", views.spectateur_dashboard, name="spectateur_dashboard"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/qr.png", views.qr_image, name="qr_image"),
    path("<uuid:pk>/pdf/", views.ticket_pdf, name="ticket_pdf"),
]
