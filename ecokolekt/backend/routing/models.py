from django.conf import settings
from django.contrib.gis.db import models as gis
from django.db import models


class Route(models.Model):
    """Tournée courante d'un collecteur — recalculée à chaque événement (nouvelle demande, scan, GPS)."""

    collector = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="route")
    origin = gis.PointField(geography=True, srid=4326, null=True)
    total_distance_m = models.PositiveIntegerField(default=0)
    total_duration_s = models.PositiveIntegerField(default=0)
    geometry = models.JSONField(null=True, blank=True)  # GeoJSON LineString
    engine = models.CharField(max_length=12, default="haversine")  # osrm | haversine
    computed_at = models.DateTimeField(auto_now=True)


class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    pickup = models.OneToOneField("waste.PickupRequest", on_delete=models.CASCADE, related_name="route_stop")
    sequence = models.PositiveSmallIntegerField()
    eta_seconds = models.PositiveIntegerField(default=0)
    leg_distance_m = models.PositiveIntegerField(default=0)
    leg_duration_s = models.PositiveIntegerField(default=0)
    over_capacity = models.BooleanField(default=False)

    class Meta:
        ordering = ["sequence"]
