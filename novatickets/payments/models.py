from django.conf import settings
from django.db import models
from django.urls import reverse

from tickets.models import Order, make_reference


class Payment(models.Model):
    """Un paiement de l'utilisateur : achat de tickets ou création d'une carte de visite."""

    class Purpose(models.TextChoices):
        TICKET = "ticket", "Achat de tickets"
        CARD = "card", "Carte de visite"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        SUCCEEDED = "succeeded", "Validé"
        FAILED = "failed", "Échoué"
        REFUNDED = "refunded", "Remboursé"

    reference = models.CharField(max_length=20, unique=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="payments")
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    business_card = models.ForeignKey(
        "cards.BusinessCard", null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    amount = models.PositiveIntegerField("montant (FCFA)")
    method = models.CharField(max_length=30, blank=True)
    payer_phone = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider = models.CharField(max_length=30, blank=True)
    provider_reference = models.CharField(max_length=80, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = make_reference("PAY", Payment)
        super().save(*args, **kwargs)

    @property
    def is_succeeded(self):
        return self.status == self.Status.SUCCEEDED

    def get_checkout_url(self):
        return reverse("payments:checkout", args=[self.reference])

    def get_success_url(self):
        if self.order_id:
            return reverse("tickets:order_detail", args=[self.order.reference])
        if self.business_card_id:
            return reverse("cards:detail", args=[self.business_card_id])
        return reverse("core:dashboard")

    @property
    def label(self):
        if self.order_id:
            return f"{self.order.quantity} × {self.order.ticket_type.name} — {self.order.event.name}"
        if self.business_card_id:
            return f"Carte de visite — {self.business_card.company_name}"
        return "Paiement"


class Withdrawal(models.Model):
    """Retrait des gains d'un organisateur vers un moyen de paiement local."""

    class Status(models.TextChoices):
        PENDING = "pending", "En cours"
        COMPLETED = "completed", "Effectué"
        FAILED = "failed", "Échoué"

    reference = models.CharField(max_length=20, unique=True, blank=True)
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="withdrawals")
    amount = models.PositiveIntegerField("montant (FCFA)")
    method = models.CharField(max_length=30)
    phone = models.CharField(max_length=40)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_reference = models.CharField(max_length=80, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.amount} FCFA"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = make_reference("RET", Withdrawal)
        super().save(*args, **kwargs)

    @property
    def method_label(self):
        from .methods import method_label
        return method_label(self.method)
