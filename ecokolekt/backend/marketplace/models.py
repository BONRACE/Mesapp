"""Marché des matières recyclées : annonces de vendeurs (collecteurs / recycleurs) et commandes.

Montants en FCFA (entiers, pas de centimes). Le stock est *réservé* à la création de la commande
et restitué si elle est annulée ou expire sans paiement.
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.contrib.gis.db import models as gis
from django.core.validators import MinValueValidator
from django.db import models

from waste.models import WasteCategory


def commission_for(subtotal: int) -> int:
    rate = Decimal(str(settings.MARKET_COMMISSION_RATE))
    return int((Decimal(subtotal) * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class Listing(models.Model):
    class Grade(models.TextChoices):
        RAW = "raw", "Brut / non trié"
        SORTED = "sorted", "Trié"
        CLEAN = "clean", "Trié et propre"
        BALED = "baled", "Pressé en balles"

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings")
    category = models.ForeignKey(WasteCategory, on_delete=models.PROTECT, related_name="listings")
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True, max_length=1500)
    grade = models.CharField(max_length=8, choices=Grade.choices, default=Grade.SORTED)
    quantity_kg = models.DecimalField(
        max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0"))],
        help_text="Stock disponible (hors quantités réservées par des commandes en cours).",
    )
    unit_price = models.PositiveIntegerField(help_text="FCFA par kg")
    min_order_kg = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("10"))
    address = models.CharField(max_length=255, blank=True)
    location = gis.PointField(geography=True, srid=4326, null=True, blank=True)
    photo = models.ImageField(upload_to="listings/", null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["is_active", "category"])]

    def __str__(self):
        return self.title

    @property
    def in_stock(self) -> bool:
        return self.is_active and self.quantity_kg >= self.min_order_kg


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "En attente de paiement"
        PAID = "paid", "Payée"
        SHIPPED = "shipped", "Expédiée"
        DELIVERED = "delivered", "Livrée"
        CANCELLED = "cancelled", "Annulée"
        EXPIRED = "expired", "Expirée"

    RELEASES_STOCK = (Status.CANCELLED, Status.EXPIRED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchases")
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")
    listing = models.ForeignKey(Listing, on_delete=models.PROTECT, related_name="orders")
    quantity_kg = models.DecimalField(max_digits=9, decimal_places=2)
    unit_price = models.PositiveIntegerField(help_text="Prix figé à la commande")
    total = models.PositiveIntegerField(help_text="Montant payé par l'acheteur (FCFA)")
    commission = models.PositiveIntegerField(default=0, help_text="Part de la plateforme (FCFA)")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING_PAYMENT, db_index=True)
    delivery_address = models.CharField(max_length=255, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    @property
    def seller_net(self) -> int:
        return self.total - self.commission
