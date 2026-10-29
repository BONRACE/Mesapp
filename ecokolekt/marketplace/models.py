from django.conf import settings
from django.db import models
from django.utils import timezone

from operations.models import Site, WasteCategory
from traceability.models import WasteBatch


class Listing(models.Model):
    """Offre de matières recyclées publiée par un centre de recyclage ou un grossiste."""

    class Status(models.TextChoices):
        ACTIVE = "active", "En vente"
        PAUSED = "paused", "En pause"
        SOLD_OUT = "sold_out", "Épuisé"

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings")
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT, related_name="listings")
    batch = models.ForeignKey(
        WasteBatch, null=True, blank=True, on_delete=models.SET_NULL, related_name="listings",
        help_text="Lot d'origine : permet de relier l'offre à sa traçabilité.",
    )
    site = models.ForeignKey(Site, null=True, blank=True, on_delete=models.SET_NULL, related_name="listings")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    available_kg = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_kg_xof = models.PositiveIntegerField("prix au kg (XOF)")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "category"])]

    def __str__(self):
        return self.title


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "En attente de paiement"
        PAID = "paid", "Payée"
        CANCELLED = "cancelled", "Annulée"

    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases")
    listing = models.ForeignKey(Listing, on_delete=models.PROTECT, related_name="orders")
    quantity_kg = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price_xof = models.PositiveIntegerField("prix unitaire figé (XOF)")
    subtotal_xof = models.PositiveIntegerField()
    commission_xof = models.PositiveIntegerField()
    seller_payout_xof = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_PAYMENT)
    created_at = models.DateTimeField(default=timezone.now)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Commande #{self.pk} — {self.listing}"

    @property
    def total_xof(self):
        return self.subtotal_xof
