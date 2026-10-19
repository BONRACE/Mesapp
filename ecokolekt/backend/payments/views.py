from django.conf import settings
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from marketplace.models import Order
from marketplace.services import MarketError

from .models import Payment
from .providers import ProviderError
from .services import finalize_payment, initiate_payment, refresh_payment


class PaymentSerializer(serializers.ModelSerializer):
    order_status = serializers.CharField(source="order.status", read_only=True)

    class Meta:
        model = Payment
        fields = ("id", "order", "order_status", "provider", "method", "amount", "currency", "status",
                  "checkout_url", "created_at")
        read_only_fields = fields


class InitiateSerializer(serializers.Serializer):
    order = serializers.UUIDField()
    method = serializers.ChoiceField(choices=Payment.Method.choices, default=Payment.Method.MOBILE_MONEY)


class InitiatePaymentView(APIView):
    def post(self, request):
        s = InitiateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            payment = initiate_payment(s.validated_data["order"], request.user, s.validated_data["method"])
        except MarketError as e:
            return Response({"detail": str(e)}, status=e.http_status)
        except ProviderError as e:
            return Response({"detail": str(e)}, status=502)
        return Response(PaymentSerializer(payment).data, status=201)


class PaymentDetailView(APIView):
    """Interrogé par le frontend au retour de la passerelle."""

    def get(self, request, pk):
        payment = Payment.objects.select_related("order").filter(pk=pk, payer=request.user).first()
        if not payment:
            return Response(status=404)
        return Response(PaymentSerializer(refresh_payment(payment)).data)


def _event_entity_id(payload: dict):
    """Identifiant de transaction d'un webhook : FedaPay (JSON imbriqué) ou CinetPay (formulaire `cpm_trans_id`)."""
    if payload.get("cpm_trans_id"):
        return str(payload["cpm_trans_id"])
    for obj in (payload.get("entity"), payload.get("data"), payload.get("object")):
        if isinstance(obj, dict) and obj.get("id") is not None:
            return str(obj["id"])
    return str(payload["object_id"]) if payload.get("object_id") is not None else None


class WebhookView(APIView):
    """Notification de la passerelle. Le contenu n'est PAS cru : on relit le statut chez le fournisseur."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def get(self, request, provider):
        """CinetPay vérifie que l'URL de notification répond 200 en GET."""
        return Response({"ok": True})

    def post(self, request, provider):
        ref = _event_entity_id(request.data if isinstance(request.data, dict) else {})
        if not ref:
            return Response({"detail": "Événement non reconnu."}, status=400)
        payment = Payment.objects.filter(provider=provider, provider_ref=ref).first()
        if payment:
            refresh_payment(payment)
        return Response({"received": True})


class MockConfirmView(APIView):
    """Simule la page de la passerelle (développement/démo uniquement)."""

    def post(self, request, pk):
        if settings.PAYMENT_DEFAULT_PROVIDER != "mock":
            return Response(status=404)
        payment = Payment.objects.filter(pk=pk, payer=request.user, provider="mock").first()
        if not payment:
            return Response(status=404)
        outcome = Payment.Status.SUCCEEDED if request.data.get("outcome", "success") == "success" else Payment.Status.FAILED
        return Response(PaymentSerializer(finalize_payment(payment.pk, outcome)).data)
