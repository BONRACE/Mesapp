from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CollectorProfile
from accounts.permissions import IsAdminRole, IsCollector
from accounts.serializers import point_from
from waste.models import PickupRequest

from .serializers import OptimizeSerializer, RouteSerializer
from .services import optimize_route


class MyRouteView(APIView):
    """Tournée du collecteur, recalculée à chaque appel depuis sa dernière position (routage dynamique)."""

    permission_classes = [IsCollector]

    def _ctx(self, request):
        return {"request": request}

    def get(self, request):
        route = optimize_route(request.user)
        return Response(RouteSerializer(route, context=self._ctx(request)).data)

    def post(self, request):
        """Recalcul depuis une position précise (ex. juste après un scan ou un changement de plan)."""
        s = OptimizeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        route = optimize_route(request.user, origin=point_from(s.validated_data))
        return Response(RouteSerializer(route, context=self._ctx(request)).data)


class LiveCollectorsView(APIView):
    """Carte temps réel de l'administration : collecteurs en service et leur charge."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        fresh = timezone.now() - timedelta(minutes=10)
        active = Count("user__assigned_pickups", filter=Q(user__assigned_pickups__status__in=PickupRequest.ACTIVE))
        rows = (
            CollectorProfile.objects.filter(user__is_active=True, is_on_duty=True, current_location__isnull=False)
            .select_related("user").annotate(active_pickups=active)
        )
        return Response(
            [
                {"id": str(c.user_id), "name": c.user.full_name, "vehicle": c.vehicle_type, "lat": c.current_location.y,
                 "lng": c.current_location.x, "active_pickups": c.active_pickups, "capacity_kg": c.capacity_kg,
                 "stale": bool(c.last_seen and c.last_seen < fresh)}
                for c in rows
            ]
        )
