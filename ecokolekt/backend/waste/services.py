import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from accounts.models import CollectorProfile, User

from . import qr
from .models import PickupRequest


class PickupError(Exception):
    def __init__(self, message, http_status=400):
        super().__init__(message)
        self.http_status = http_status


def assign_nearest_collector(pickup: PickupRequest, radius_m: int | None = None):
    """Affecte la demande au collecteur en service le moins chargé, puis le plus proche (PostGIS)."""
    radius_m = radius_m or settings.AUTO_ASSIGN_RADIUS_M
    active = Q(user__assigned_pickups__status__in=PickupRequest.ACTIVE)
    candidate = (
        CollectorProfile.objects.filter(
            is_on_duty=True,
            user__is_approved=True,
            user__is_active=True,
            current_location__dwithin=(pickup.location, D(m=radius_m)),
        )
        .annotate(distance=Distance("current_location", pickup.location), load=Count("user__assigned_pickups", filter=active))
        .order_by("load", "distance")
        .first()
    )
    if not candidate:
        return None
    pickup.collector = candidate.user
    pickup.status = PickupRequest.Status.ASSIGNED
    pickup.save(update_fields=["collector", "status"])
    return candidate.user


def auto_assign_pending() -> int:
    n = 0
    for p in PickupRequest.objects.filter(status=PickupRequest.Status.PENDING, collector__isnull=True):
        if assign_nearest_collector(p):
            n += 1
    return n


def complete_pickup(collector: User, token: str, weight_kg: Decimal, point) -> PickupRequest:
    """Valide un scan de QR : signature, usage unique, collecteur assigné, proximité GPS (point obligatoire)."""
    try:
        pickup_id, nonce = qr.parse_token(token)
    except qr.InvalidToken as e:
        raise PickupError(str(e), 400)
    with transaction.atomic():
        pickup = (
            PickupRequest.objects.select_for_update().select_related("category", "citizen").filter(pk=pickup_id).first()
        )
        if not pickup or pickup.qr_nonce != nonce or pickup.qr_used_at:
            raise PickupError("Ce QR code a déjà été utilisé ou n'est plus valide.", 409)
        if pickup.collector_id != collector.id:
            raise PickupError("Cette demande n'est pas dans votre tournée.", 403)
        if pickup.status not in PickupRequest.ACTIVE:
            raise PickupError("Cette demande n'est plus à collecter.", 409)
        dist = PickupRequest.objects.filter(pk=pickup.pk).annotate(d=Distance("location", point)).values_list("d", flat=True).first()
        if dist is None or dist.m > settings.QR_MAX_DISTANCE_M:
            where = f"à {int(dist.m)} m" if dist is not None else "trop loin"
            raise PickupError(f"Vous êtes {where} du ménage. Rapprochez-vous pour valider.", 403)
        now = timezone.now()
        points = int(weight_kg * pickup.category.points_per_kg)
        pickup.status = PickupRequest.Status.COLLECTED
        pickup.actual_weight_kg = weight_kg
        pickup.collected_at = now
        pickup.qr_used_at = now
        pickup.qr_nonce = secrets.token_hex(6)
        pickup.points_awarded = points
        pickup.save()
        User.objects.filter(pk=pickup.citizen_id).update(eco_points=F("eco_points") + points)
    return pickup

