import phonenumbers
from django.conf import settings
from django.contrib.gis.geos import Point
from rest_framework import serializers

from .models import CollectorProfile, RecyclerProfile, User


def normalize_phone(raw: str) -> str:
    try:
        num = phonenumbers.parse(raw, settings.DEFAULT_PHONE_REGION)
    except phonenumbers.NumberParseException:
        raise serializers.ValidationError("Numéro de téléphone invalide.")
    if not phonenumbers.is_valid_number(num):
        raise serializers.ValidationError("Numéro de téléphone invalide.")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


class PhoneField(serializers.CharField):
    def to_internal_value(self, data):
        return normalize_phone(super().to_internal_value(data))


class RequestOTPSerializer(serializers.Serializer):
    phone = PhoneField()


class VerifyOTPSerializer(serializers.Serializer):
    phone = PhoneField()
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Le code contient 6 chiffres."})


class LatLngMixin(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False, write_only=True)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False, write_only=True)

    def validate(self, attrs):
        if ("latitude" in attrs) != ("longitude" in attrs):
            raise serializers.ValidationError("Latitude et longitude vont ensemble.")
        return attrs


def point_from(attrs):
    if "latitude" in attrs:
        return Point(attrs["longitude"], attrs["latitude"], srid=4326)
    return None


class UserSerializer(serializers.ModelSerializer):
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    collector = serializers.SerializerMethodField()
    recycler = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", "phone", "full_name", "role", "is_approved", "profile_completed", "eco_points",
            "latitude", "longitude", "collector", "recycler", "date_joined",
        )
        read_only_fields = fields

    def get_latitude(self, u):
        return u.location.y if u.location else None

    def get_longitude(self, u):
        return u.location.x if u.location else None

    def get_collector(self, u):
        c = getattr(u, "collector", None)
        return c and {"vehicle_type": c.vehicle_type, "capacity_kg": c.capacity_kg, "is_on_duty": c.is_on_duty}

    def get_recycler(self, u):
        r = getattr(u, "recycler", None)
        return r and {"company_name": r.company_name, "address": r.address}


class ProfileUpdateSerializer(LatLngMixin):
    full_name = serializers.CharField(min_length=2, max_length=120, required=False)
    role = serializers.ChoiceField(
        choices=[User.Role.CITIZEN, User.Role.COLLECTOR, User.Role.RECYCLER], required=False
    )
    vehicle_type = serializers.ChoiceField(choices=CollectorProfile.Vehicle.choices, required=False)
    capacity_kg = serializers.IntegerField(min_value=10, max_value=20000, required=False)
    company_name = serializers.CharField(max_length=140, required=False, allow_blank=True)
    address = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def save_for(self, user: User) -> User:
        d = self.validated_data
        if "role" in d and not user.profile_completed and user.role != User.Role.ADMIN:
            user.role = d["role"]
            user.is_approved = user.role == User.Role.CITIZEN or settings.AUTO_APPROVE_PROFESSIONALS
        if "full_name" in d:
            user.full_name = d["full_name"]
        if (pt := point_from(d)) is not None:
            user.location = pt
        if user.full_name:
            user.profile_completed = True
        user.save()
        if user.role == User.Role.COLLECTOR:
            c, _ = CollectorProfile.objects.get_or_create(user=user)
            for f in ("vehicle_type", "capacity_kg"):
                if f in d:
                    setattr(c, f, d[f])
            c.save()
        elif user.role == User.Role.RECYCLER:
            r, _ = RecyclerProfile.objects.get_or_create(user=user)
            for f in ("company_name", "address"):
                if f in d:
                    setattr(r, f, d[f])
            r.save()
        return user


class LocationSerializer(LatLngMixin):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    is_on_duty = serializers.BooleanField(required=False)
