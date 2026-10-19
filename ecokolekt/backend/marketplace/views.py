from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.db.models import Avg, Count, Min, Sum
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import IsSeller

from .models import Listing, Order
from .serializers import ListingSerializer, OrderCreateSerializer, OrderSerializer
from .services import MarketError, cancel_order, deliver_order, expire_stale_orders, place_order, ship_order
from waste.models import WasteCategory


class ListingViewSet(viewsets.ModelViewSet):
    """Lecture publique ; écriture réservée aux collecteurs/recycleurs approuvés, sur leurs propres annonces."""

    serializer_class = ListingSerializer
    filterset_fields = {"category": ["exact"], "grade": ["exact"], "unit_price": ["gte", "lte"]}
    search_fields = ["title", "description", "address"]
    ordering_fields = ["unit_price", "created_at", "quantity_kg"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        return [IsSeller()]

    def get_queryset(self):
        qs = Listing.objects.select_related("category", "seller", "seller__recycler")
        u, p = self.request.user, self.request.query_params
        if self.action in ("update", "partial_update", "destroy") or p.get("mine") == "1":
            qs = qs.filter(seller=u) if u.is_authenticated else qs.none()
        else:
            qs = qs.filter(is_active=True, quantity_kg__gt=0)
        if p.get("lat") and p.get("lng"):
            here = Point(float(p["lng"]), float(p["lat"]), srid=4326)
            qs = qs.filter(location__isnull=False).annotate(distance=Distance("location", here))
            if p.get("radius_km"):
                qs = qs.filter(location__dwithin=(here, D(km=float(p["radius_km"]))))
            if p.get("sort") == "distance":
                qs = qs.order_by("distance")
        return qs

    def perform_destroy(self, instance):
        # Les commandes référencent l'annonce : on la retire du marché sans la supprimer.
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class OrderViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = OrderSerializer
    filterset_fields = ["status"]
    ordering_fields = ["created_at", "total"]

    def get_queryset(self):
        qs = Order.objects.select_related("listing", "listing__category", "buyer", "buyer__recycler", "seller", "seller__recycler")
        u = self.request.user
        if u.role == User.Role.ADMIN:
            return qs
        if self.request.query_params.get("as") == "seller":
            return qs.filter(seller=u)
        return qs.filter(buyer=u)

    def list(self, request, *args, **kwargs):
        expire_stale_orders()
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        s = OrderCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            order = place_order(request.user, d["listing"], d["quantity_kg"], d["delivery_address"], d["notes"])
        except MarketError as e:
            return Response({"detail": str(e)}, status=e.http_status)
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    def _own(self, pk, field):
        return Order.objects.select_related("listing", "listing__category", "buyer", "seller").filter(pk=pk, **{field: self.request.user}).first()

    def _transition(self, pk, field, fn):
        order = self._own(pk, field)
        if not order:
            return Response(status=404)
        try:
            order = fn(order)
        except MarketError as e:
            return Response({"detail": str(e)}, status=e.http_status)
        return Response(self.get_serializer(order).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(pk, "buyer", lambda o: cancel_order(o.pk))

    @action(detail=True, methods=["post"], permission_classes=[IsSeller])
    def ship(self, request, pk=None):
        return self._transition(pk, "seller", ship_order)

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        """Confirmation de réception par l'acheteur."""
        return self._transition(pk, "buyer", deliver_order)


class PriceBoardView(APIView):
    """Cours indicatifs par catégorie, calculés sur les annonces actives (public)."""

    permission_classes = [AllowAny]

    def get(self, request):
        rows = (
            Listing.objects.filter(is_active=True, quantity_kg__gt=0)
            .values("category__id", "category__name", "category__color")
            .annotate(avg_price=Avg("unit_price"), min_price=Min("unit_price"), kg=Sum("quantity_kg"), listings=Count("id"))
            .order_by("category__name")
        )
        return Response(
            [
                {"category": r["category__id"], "name": r["category__name"], "color": r["category__color"],
                 "avg_price": round(r["avg_price"]), "min_price": r["min_price"], "kg": r["kg"], "listings": r["listings"]}
                for r in rows
            ]
        )


class EarningsView(APIView):
    """Revenus du vendeur : ventes payées, commission plateforme, net, commandes à expédier."""

    permission_classes = [IsSeller]

    def get(self, request):
        done = Order.objects.filter(seller=request.user, status__in=[Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED])
        agg = done.aggregate(gross=Sum("total"), fee=Sum("commission"), kg=Sum("quantity_kg"), n=Count("id"))
        gross, fee = agg["gross"] or 0, agg["fee"] or 0
        return Response(
            {
                "gross_xof": gross, "commission_xof": fee, "net_xof": gross - fee, "kg_sold": agg["kg"] or 0,
                "orders": agg["n"], "to_ship": done.filter(status=Order.Status.PAID).count(),
                "active_listings": Listing.objects.filter(seller=request.user, is_active=True, quantity_kg__gt=0).count(),
            }
        )
