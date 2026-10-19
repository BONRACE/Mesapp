from django.urls import path

from . import views

urlpatterns = [
    path("initiate/", views.InitiatePaymentView.as_view()),
    path("<uuid:pk>/", views.PaymentDetailView.as_view()),
    path("mock/<uuid:pk>/confirm/", views.MockConfirmView.as_view()),
    path("webhook/<slug:provider>/", views.WebhookView.as_view()),
]
