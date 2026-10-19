from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminRole, IsCitizen, IsCollector
from routing.models import RouteStop
from routing.serializers import RouteSerializer
from routing.services import haversine_m, optimize_route

from . import qr
from .models import CollectionPoint, PickupRequest, WasteCategory
from .serializers import CollectionPointSerializer, PickupSerializer, ScanSerializer, WasteCategorySerializer
from .services import PickupError, assign_nearest_collector, auto_assign_pending, complete_pickup


class WasteCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WasteCategory.objects.all().order_by("id")
    serializer_class = WasteCategorySerializer
    pagination_class = None


class CollectionPointViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CollectionPointSerializer
    filterset_fields = ["kind", "categories"]
    pagination_class = None

    def get_queryset(self):
        qs = CollectionPoint.objects.filter(is_active=True).prefetch_related("categories")
        p = self.request.query_params
        if p.get("lat") and p.get("lng"):
            here = Point(float(p["lng"]), float(p["lat"]), srid=4326)
            qs = qs.annotate(distance=Distance("location", here)).order_by("distance")
            if p.get("radius_km"):
                qs = qs.filter(location__dwithin=(here, D(km=float(p["radius_km"]))))
        return qs


class PickupViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = PickupSerializer
    filterset_fields = ["status", "category"]
    ordering_fields = ["created_at"]

    def get_permissions(self):
        if self.action in ("create", "qr", "cancel", "tracking"):
            return [IsCitizen()]
        if self.action in ("available", "accept", "start", "scan"):
            return [IsCollector()]
        return [IsAuthenticated()]

    def get_queryset(self):
        u = self.request.user
        qs = PickupRequest.objects.select_related("category", "citizen")
        if u.role == User.Role.CITIZEN:
            return qs.filter(citizen=u)
        if u.role == User.Role.COLLECTOR:
            return qs.filter(collector=u)
        if u.role == User.Role.ADMIN:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        pickup = serializer.save()
        assign_nearest_collector(pickup)  # si aucun collecteur proche en service, reste "en attente"

    @action(detail=True, methods=["get"])
    def qr(self, request, pk=None):
        pickup = self.get_object()
        if pickup.status not in (PickupRequest.Status.PENDING, *PickupRequest.ACTIVE):
            return Response({"detail": "Ce QR code n'est plus actif."}, status=410)
        return HttpResponse(qr.render_png(qr.make_token(pickup)), content_type="image/png")

    @action(detail=True, methods=["get"])
    def tracking(self, request, pk=None):
        """Suivi côté citoyen : position du collecteur, distance et ETA estimée."""
        pickup = self.get_object()
        out = {"status": pickup.status, "collector": None}
        if pickup.status not in PickupRequest.ACTIVE or not pickup.collector_id:
            return Response(out)
        loc = getattr(getattr(pickup.collector, "collector", None), "current_location", None)
        stop = RouteStop.objects.filter(pickup=pickup).first()
        out["collector"] = {
            "name": pickup.collector.full_name,
            "lat": loc.y if loc else None,
            "lng": loc.x if loc else None,
            "distance_m": int(haversine_m((loc.y, loc.x), (pickup.location.y, pickup.location.x))) if loc else None,
            "eta_seconds": stop.eta_seconds if stop else None,
            "stops_before": (stop.sequence - 1) if stop else None,
        }
        return Response(out)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Chiffres clés pour les tableaux de bord citoyen et collecteur."""
        u = request.user
        done = PickupRequest.objects.filter(status=PickupRequest.Status.COLLECTED)
        if u.role == User.Role.COLLECTOR:
            mine = done.filter(collector=u)
            start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
            today = mine.filter(collected_at__gte=start)
            return Response({
                "collected_today": today.count(),
                "kg_today": today.aggregate(s=Sum("actual_weight_kg"))["s"] or 0,
                "collected_total": mine.count(),
                "kg_total": mine.aggregate(s=Sum("actual_weight_kg"))["s"] or 0,
                "active": PickupRequest.objects.filter(collector=u, status__in=PickupRequest.ACTIVE).count(),
            })
        mine = done.filter(citizen=u)
        by_cat = mine.values("category__name", "category__color").annotate(kg=Sum("actual_weight_kg")).order_by("-kg")
        return Response({
            "eco_points": u.eco_points,
            "requests_total": PickupRequest.objects.filter(citizen=u).count(),
            "collected": mine.count(),
            "kg_collected": mine.aggregate(s=Sum("actual_weight_kg"))["s"] or 0,
            "kg_by_category": list(by_cat),
        })

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        pickup = self.get_object()
        if pickup.status not in (PickupRequest.Status.PENDING, PickupRequest.Status.ASSIGNED):
            return Response({"detail": "Impossible d'annuler à ce stade."}, status=409)
        pickup.status = PickupRequest.Status.CANCELLED
        pickup.save(update_fields=["status"])
        return Response(self.get_serializer(pickup).data)

    @action(detail=False, methods=["get"])
    def available(self, request):
        """Demandes non assignées, triées par distance au collecteur."""
        qs = PickupRequest.objects.select_related("category", "citizen").filter(
            status=PickupRequest.Status.PENDING, collector__isnull=True
        )
        loc = getattr(getattr(request.user, "collector", None), "current_location", None)
        if loc:
            radius = float(request.query_params.get("radius_km", 15))
            qs = qs.filter(location__dwithin=(loc, D(km=radius))).annotate(distance=Distance("location", loc)).order_by("distance")
        return Response(self.get_serializer(qs[:50], many=True).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        with transaction.atomic():
            pickup = PickupRequest.objects.select_for_update().filter(pk=pk).first()
            if not pickup:
                return Response(status=404)
            if pickup.status != PickupRequest.Status.PENDING or pickup.collector_id:
                return Response({"detail": "Demande déjà prise en charge."}, status=409)
            pickup.collector, pickup.status = request.user, PickupRequest.Status.ASSIGNED
            pickup.save(update_fields=["collector", "status"])
        return Response(self.get_serializer(pickup).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        pickup = self.get_object()
        if pickup.status != PickupRequest.Status.ASSIGNED:
            return Response({"detail": "Statut invalide."}, status=409)
        pickup.status = PickupRequest.Status.EN_ROUTE
        pickup.save(update_fields=["status"])
        return Response(self.get_serializer(pickup).data)

    @action(detail=False, methods=["post"])
    def scan(self, request):
        s = ScanSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        point = Point(d["longitude"], d["latitude"], srid=4326)
        try:
            pickup = complete_pickup(request.user, d["token"], d["weight_kg"], point)
        except PickupError as e:
            return Response({"detail": str(e)}, status=e.http_status)
        # Re-routage dynamique depuis la position du scan
        route = None
        try:
            route = RouteSerializer(optimize_route(request.user, origin=point), context={"request": request}).data
        except Exception:  # le routage ne doit jamais bloquer une collecte validée
            pass
        return Response({"pickup": self.get_serializer(pickup).data, "route": route})

    @action(detail=False, methods=["post"], permission_classes=[IsAdminRole], url_path="auto-assign")
    def auto_assign(self, request):
        return Response({"assigned": auto_assign_pending()})
