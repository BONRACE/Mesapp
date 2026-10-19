import uuid

from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCEEDED = "succeeded", "Réussi"
        FAILED = "failed", "Échoué"

    class Method(models.TextChoices):
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        CARD = "card", "Carte bancaire"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey("marketplace.Order", on_delete=models.PROTECT, related_name="payments")
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=16)
    method = models.CharField(max_length=14, choices=Method.choices, default=Method.MOBILE_MONEY)
    amount = models.PositiveIntegerField(help_text="FCFA")
    currency = models.CharField(max_length=3, default="XOF")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider_ref = models.CharField(max_length=80, blank=True, db_index=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    needs_refund = models.BooleanField(
        default=False, help_text="Paiement reçu mais commande non honorable (expirée sans stock, ou double paiement)."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["provider", "provider_ref"])]
