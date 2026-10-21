from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("acheter/<slug:slug>/", views.buy, name="buy"),
    path("commande/<str:reference>/", views.order_detail, name="order_detail"),
    path("commande/<str:reference>/pdf/", views.order_pdf, name="order_pdf"),
    path("ticket/<str:reference>/", views.ticket_detail, name="detail"),
    path("ticket/<str:reference>/pdf/", views.ticket_pdf, name="pdf"),
    path("ticket/<str:reference>/qr.png", views.ticket_qr, name="qr"),
    path("verifier/<str:token>/", views.verify, name="verify"),
    path("verifier/<str:token>/valider/", views.mark_used, name="mark_used"),
]
