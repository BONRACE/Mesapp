from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("commande/<slug:slug>/acheter/", views.buy, name="buy"),
    path("commande/<str:reference>/payer/", views.pay, name="pay"),
    path("billet/<uuid:code>/", views.ticket_view, name="ticket"),
    path("billet/<uuid:code>/pdf/", views.ticket_pdf, name="ticket_pdf"),
    path("billet/<uuid:code>/qr.png", views.ticket_qr, name="ticket_qr"),
    path("verifier/<uuid:code>/", views.verify, name="verify"),
]
