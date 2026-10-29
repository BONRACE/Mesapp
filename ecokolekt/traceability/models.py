import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from operations.models import PickupRequest, WasteCategory


class BatchStatus(models.TextChoices):
    CREATED = "created", "Créé"
    COLLECTED = "collected", "Collecté"
    AT_CENTER = "at_center", "Réceptionné au centre"
    PROCESSED = "processed", "Traité"
    SOLD = "sold", "Vendu"


class WasteBatch(models.Model):
    """Lot de déchets tracé de bout en bout. Identifié par un UUID et un code lisible."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=24, unique=True)
    producer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="batches")
    pickup = models.OneToOneField(
        PickupRequest, null=True, blank=True, on_delete=models.SET_NULL, related_name="batch"
    )
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT, related_name="batches")
    weight_kg = models.DecimalField(max_digits=8, decimal_places=2)
    holder = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="held_batches"
    )
    status = models.CharField(max_length=20, choices=BatchStatus.choices, default=BatchStatus.CREATED)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "lot"
        verbose_name_plural = "lots"

    def __str__(self):
        return self.code


class EventType(models.TextChoices):
    CREATED = "created", "Lot créé"
    PICKED_UP = "picked_up", "Enlevé chez le producteur"
    TRANSFERRED = "transferred", "Transféré à un collecteur"
    RECEIVED = "received", "Réceptionné"
    PROCESSED = "processed", "Traité / valorisé"
    SOLD = "sold", "Vendu"


class TrackingEvent(models.Model):
    """Événement immuable. Chaque entrée référence le hash de la précédente (chaîne de hachage)."""

    batch = models.ForeignKey(WasteBatch, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    previous_hash = models.CharField(max_length=64)
    hash = models.CharField(max_length=64, db_index=True)

    class Meta:
        ordering = ["occurred_at", "id"]

    def __str__(self):
        return f"{self.batch.code} — {self.get_event_type_display()}"
