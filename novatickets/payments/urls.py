from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("payer/", views.initiate_payment, name="initiate"),
    path("webhook/", views.webhook, name="webhook"),
    path("<uuid:pk>/", views.payment_status, name="status"),
    path("<uuid:pk>/statut.json", views.payment_status_json, name="status_json"),
    path("<uuid:pk>/recu.pdf", views.receipt_pdf, name="receipt_pdf"),
    path("<uuid:pk>/simulation/", views.simulate_callback, name="simulate"),
]
