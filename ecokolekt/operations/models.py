from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

LATITUDE_VALIDATORS = [MinValueValidator(-90), MaxValueValidator(90)]
LONGITUDE_VALIDATORS = [MinValueValidator(-180), MaxValueValidator(180)]


class WasteCategory(models.Model):
    code = models.SlugField(unique=True)
    label = models.CharField("libellé", max_length=80)
    reference_price_xof = models.PositiveIntegerField("prix de référence (XOF/kg)", default=0)
    recyclable = models.BooleanField(default=True)

    class Meta:
        ordering = ["label"]
        verbose_name = "catégorie de déchet"
        verbose_name_plural = "catégories de déchets"

    def __str__(self):
        return self.label


class Site(models.Model):
    """Lieu géolocalisé : site de production, point de collecte ou centre de recyclage."""

    class Kind(models.TextChoices):
        PRODUCTION = "production", "Site de production"
        COLLECTION = "collection", "Point de collecte"
        RECYCLING = "recycling", "Centre de recyclage"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sites")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField("latitude", validators=LATITUDE_VALIDATORS)
    longitude = models.FloatField("longitude", validators=LONGITUDE_VALIDATORS)
    accepted_categories = models.ManyToManyField(WasteCategory, blank=True, related_name="sites")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["kind", "owner"]),
            models.Index(fields=["latitude", "longitude"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"


class PickupStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    SCHEDULED = "scheduled", "Planifiée"
    COLLECTED = "collected", "Collectée"
    CANCELLED = "cancelled", "Annulée"


class Route(models.Model):
    """Tournée d'un collecteur pour une journée donnée."""

    class Status(models.TextChoices):
        PLANNED = "planned", "Planifiée"
        IN_PROGRESS = "in_progress", "En cours"
        DONE = "done", "Terminée"

    collector = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="routes")
    planned_for = models.DateField()
    origin_latitude = models.FloatField(validators=LATITUDE_VALIDATORS)
    origin_longitude = models.FloatField(validators=LONGITUDE_VALIDATORS)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    total_distance_m = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-planned_for", "-created_at"]

    def __str__(self):
        return f"Tournée {self.planned_for:%d/%m/%Y} — {self.collector}"


class PickupRequest(models.Model):
    """Demande d'enlèvement émise par un producteur."""

    producer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pickup_requests")
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="pickups")
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT, related_name="pickups")
    estimated_kg = models.DecimalField(max_digits=8, decimal_places=2)
    actual_kg = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=PickupStatus.choices, default=PickupStatus.PENDING)
    collector = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="assigned_pickups",
    )
    route = models.ForeignKey(Route, null=True, blank=True, on_delete=models.SET_NULL, related_name="stops")
    stop_order = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["window_start"]
        indexes = [
            models.Index(fields=["status", "window_start"]),
            models.Index(fields=["route", "stop_order"]),
        ]

    def __str__(self):
        return f"Enlèvement #{self.pk} — {self.category} ({self.estimated_kg} kg)"
