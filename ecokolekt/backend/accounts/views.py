from django.conf import settings
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CollectorProfile, User
from .otp import OTPError, issue_otp, send_sms, verify_otp
from .permissions import IsAdminRole, IsCollector
from .serializers import (
    LocationSerializer, ProfileUpdateSerializer, RequestOTPSerializer, UserSerializer,
    VerifyOTPSerializer, point_from,
)


class RequestOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"

    def post(self, request):
        s = RequestOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        phone = s.validated_data["phone"]
        try:
            code = issue_otp(phone)
        except OTPError as e:
            return Response({"detail": str(e), "retry_after": e.retry_after}, status=429)
        send_sms(phone, f"EcoKolekt : votre code est {code}. Valable {settings.OTP_TTL_SECONDS // 60} minutes.")
        data = {"detail": "Code envoyé.", "phone": phone, "resend_in": settings.OTP_RESEND_SECONDS}
        if settings.DEBUG and settings.SMS_BACKEND == "console":
            data["dev_code"] = code  # jamais exposé en production
        return Response(data)


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        s = VerifyOTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        phone, code = s.validated_data["phone"], s.validated_data["code"]
        try:
            verify_otp(phone, code)
        except OTPError as e:
            return Response({"detail": str(e)}, status=400)
        user = User.objects.filter(phone=phone).first()
        is_new = user is None
        if is_new:
            user = User.objects.create_user(phone=phone)
        if not user.is_active:
            return Response({"detail": "Compte désactivé."}, status=403)
        refresh = RefreshToken.for_user(user)
        refresh["role"] = user.role
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "is_new": is_new,
                "user": UserSerializer(user).data,
            }
        )


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        s = ProfileUpdateSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        user = s.save_for(request.user)
        return Response(UserSerializer(user).data)


class CollectorLocationView(APIView):
    """Position GPS du collecteur (appelée toutes les ~20 s par l'app) + état de service."""

    permission_classes = [IsCollector]

    def post(self, request):
        s = LocationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        profile, _ = CollectorProfile.objects.get_or_create(user=request.user)
        profile.current_location = point_from(s.validated_data)
        profile.last_seen = timezone.now()
        if "is_on_duty" in s.validated_data:
            profile.is_on_duty = s.validated_data["is_on_duty"]
        profile.save()
        return Response({"is_on_duty": profile.is_on_duty, "last_seen": profile.last_seen})


# --- Administration ---------------------------------------------------------
class AdminUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = tuple(f for f in UserSerializer.Meta.fields if f != "is_approved")


class AdminUserList(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = AdminUserSerializer
    filterset_fields = ["role", "is_approved"]
    search_fields = ["phone", "full_name"]
    queryset = User.objects.select_related("collector", "recycler").order_by("-date_joined")


class AdminUserApprove(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        approved = bool(request.data.get("approved", True))
        n = User.objects.filter(pk=pk).update(is_approved=approved)
        return Response({"updated": n})


class AdminStatsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        from marketplace.models import Order
        from waste.models import PickupRequest

        pk = PickupRequest.objects
        by_status = dict(pk.values_list("status").annotate(n=Count("id")))
        collected = pk.filter(status=PickupRequest.Status.COLLECTED)
        kg_by_cat = list(
            collected.values("category__name", "category__color").annotate(kg=Sum("actual_weight_kg")).order_by("-kg")
        )
        paid = Order.objects.filter(status__in=[Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED])
        return Response(
            {
                "users": dict(User.objects.values_list("role").annotate(n=Count("id"))),
                "pending_approvals": User.objects.filter(is_approved=False).count(),
                "pickups_by_status": by_status,
                "kg_collected": collected.aggregate(s=Sum("actual_weight_kg"))["s"] or 0,
                "kg_by_category": kg_by_cat,
                "market": {
                    "orders_paid": paid.count(),
                    "gmv_xof": paid.aggregate(s=Sum("total"))["s"] or 0,
                    "commission_xof": paid.aggregate(s=Sum("commission"))["s"] or 0,
                },
            }
        )
