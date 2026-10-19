from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("listings", views.ListingViewSet, basename="listing")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("prices/", views.PriceBoardView.as_view()),
    path("earnings/", views.EarningsView.as_view()),
] + router.urls
