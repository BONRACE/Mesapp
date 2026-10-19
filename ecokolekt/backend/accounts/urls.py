from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("auth/otp/request/", views.RequestOTPView.as_view()),
    path("auth/otp/verify/", views.VerifyOTPView.as_view()),
    path("auth/token/refresh/", TokenRefreshView.as_view()),
    path("me/", views.MeView.as_view()),
    path("me/location/", views.CollectorLocationView.as_view()),
    path("admin/stats/", views.AdminStatsView.as_view()),
    path("admin/users/", views.AdminUserList.as_view()),
    path("admin/users/<uuid:pk>/approve/", views.AdminUserApprove.as_view()),
]
