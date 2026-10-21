from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("payer/<str:reference>/", views.checkout, name="checkout"),
    path("historique/", views.history, name="history"),
    path("retraits/", views.withdrawals, name="withdrawals"),
]
