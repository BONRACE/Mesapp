from rest_framework import serializers

from accounts.serializers import LatLngMixin
from waste.serializers import PickupSerializer

from .models import Route, RouteStop


class RouteStopSerializer(serializers.ModelSerializer):
    pickup = PickupSerializer(read_only=True)

    class Meta:
        model = RouteStop
        fields = ("sequence", "eta_seconds", "leg_distance_m", "leg_duration_s", "over_capacity", "pickup")


class RouteSerializer(serializers.ModelSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)
    origin = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = ("engine", "total_distance_m", "total_duration_s", "computed_at", "origin", "geometry", "stops")

    def get_origin(self, o):
        return {"lat": o.origin.y, "lng": o.origin.x} if o.origin else None


class OptimizeSerializer(LatLngMixin):
    """Position de départ facultative ; à défaut, dernière position GPS connue du collecteur."""
