from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("mes-tickets/", views.mes_tickets, name="mes_tickets"),
    path("acheter/<slug:slug>/", views.acheter, name="acheter"),
    path("commande/<str:reference>/paiement/", views.paiement, name="paiement"),
    path("<str:reference>/", views.ticket_detail, name="ticket"),
    path("<str:reference>/pdf/", views.ticket_pdf, name="ticket_pdf"),
]
