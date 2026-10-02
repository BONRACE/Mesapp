from django.urls import path
from . import views
from . import views_paiement

app_name = "tickets"

urlpatterns = [
    path("mon-espace/", views.spectateur_dashboard, name="spectateur_dashboard"),
    path("organisateur/retraits/", views.retraits, name="retraits"),
    path("paiement/retour/", views_paiement.paiement_retour, name="paiement_retour"),
    path("paiement/webhook/fedapay/", views_paiement.fedapay_webhook, name="fedapay_webhook"),
    path("<uuid:pk>/", views.detail, name="detail"),
    path("<uuid:pk>/qr.png", views.qr_image, name="qr_image"),
    path("<uuid:pk>/pdf/", views.ticket_pdf, name="ticket_pdf"),
]
