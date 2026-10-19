from decimal import Decimal

from rest_framework import serializers

from accounts.serializers import LatLngMixin, point_from

from .models import CollectionPoint, PickupRequest, WasteCategory


class WasteCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WasteCategory
        fields = ("id", "code", "name", "color", "points_per_kg", "is_recyclable")


class CollectionPointSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    distance_m = serializers.SerializerMethodField()
    categories = WasteCategorySerializer(many=True, read_only=True)

    class Meta:
        model = CollectionPoint
        fields = ("id", "name", "kind", "address", "opening_hours", "latitude", "longitude", "distance_m", "categories")

    def get_latitude(self, o):
        return o.location.y

    def get_longitude(self, o):
        return o.location.x

    def get_distance_m(self, o):
        d = getattr(o, "distance", None)
        return int(d.m) if d is not None else None


class PickupSerializer(LatLngMixin, serializers.ModelSerializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90, write_only=True)
    longitude = serializers.FloatField(min_value=-180, max_value=180, write_only=True)
    category_detail = WasteCategorySerializer(source="category", read_only=True)
    citizen_name = serializers.CharField(source="citizen.full_name", read_only=True)
    citizen_phone = serializers.SerializerMethodField()
    distance_m = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()

    class Meta:
        model = PickupRequest
        fields = (
            "id", "category", "category_detail", "address", "latitude", "longitude", "lat", "lng",
            "estimated_weight_kg", "actual_weight_kg", "notes", "scheduled_for", "status", "points_awarded",
            "collector", "citizen_name", "citizen_phone", "distance_m", "created_at", "collected_at",
        )
        read_only_fields = ("status", "actual_weight_kg", "points_awarded", "collector", "created_at", "collected_at")

    def get_lat(self, o):
        return o.location.y

    def get_lng(self, o):
        return o.location.x

    def get_distance_m(self, o):
        d = getattr(o, "distance", None)
        return int(d.m) if d is not None else None

    def get_citizen_phone(self, o):
        # Le numéro n'est visible que par le collecteur assigné.
        req = self.context.get("request")
        if req and req.user.id == o.collector_id:
            return o.citizen.phone
        return None

    def validate_estimated_weight_kg(self, v):
        if v <= 0 or v > Decimal("500"):
            raise serializers.ValidationError("Poids estimé entre 0,1 et 500 kg.")
        return v

    def create(self, validated):
        pt = point_from(validated)
        validated.pop("latitude"), validated.pop("longitude")
        return PickupRequest.objects.create(citizen=self.context["request"].user, location=pt, **validated)


class ScanSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=200)
    weight_kg = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.1"), max_value=Decimal("2000"))
    # Position GPS du collecteur au moment du scan : obligatoire, sinon le contrôle de proximité serait contournable.
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
