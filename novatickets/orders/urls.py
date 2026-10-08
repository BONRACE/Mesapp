from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("evenements/<int:pk>/acheter/", views.checkout, name="checkout"),
    path("commandes/<str:reference>/paiement/", views.pay, name="pay"),
    path("commandes/<str:reference>/confirmation/", views.confirmation, name="confirmation"),
    path("mon-espace/", views.my_space, name="my_space"),
    path("billets/<str:reference>/", views.ticket_view, name="ticket"),
    path("billets/<str:reference>/pdf/", views.ticket_pdf_view, name="ticket_pdf"),
    path("billets/<str:reference>/qr.png", views.ticket_qr, name="ticket_qr"),
]
