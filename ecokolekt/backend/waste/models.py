import secrets
import uuid

from django.conf import settings
from django.contrib.gis.db import models as gis
from django.db import models


class WasteCategory(models.Model):
    """Catégorie de tri. `color` suit le code couleur des bacs (jaune, bleu, vert…)."""

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    color = models.CharField(max_length=7, default="#FFC41F")
    points_per_kg = models.PositiveIntegerField(default=10)
    is_recyclable = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "waste categories"

    def __str__(self):
        return self.name


class CollectionPoint(models.Model):
    class Kind(models.TextChoices):
        BIN = "bin", "Bac de quartier"
        DROPOFF = "dropoff", "Point d'apport volontaire"
        CENTER = "center", "Centre de tri"

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.DROPOFF)
    location = gis.PointField(geography=True, srid=4326)
    address = models.CharField(max_length=255, blank=True)
    categories = models.ManyToManyField(WasteCategory, blank=True)
    opening_hours = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


def _nonce():
    return secrets.token_hex(6)


class PickupRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        ASSIGNED = "assigned", "Collecteur assigné"
        EN_ROUTE = "en_route", "Collecteur en route"
        COLLECTED = "collected", "Collecté"
        CANCELLED = "cancelled", "Annulé"

    ACTIVE = (Status.ASSIGNED, Status.EN_ROUTE)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    citizen = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pickups")
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_pickups"
    )
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT)
    address = models.CharField(max_length=255, blank=True)
    location = gis.PointField(geography=True, srid=4326)
    estimated_weight_kg = models.DecimalField(max_digits=7, decimal_places=2, default=5)
    actual_weight_kg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)

    qr_nonce = models.CharField(max_length=16, default=_nonce)
    qr_used_at = models.DateTimeField(null=True, blank=True)
    points_awarded = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
