import secrets
import string

from django.conf import settings
from django.db import models
from django.urls import reverse

from core.countries import format_phone
from events.models import Event, TicketType

_ALPHABET = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"


def make_reference(prefix: str, model, field: str = "reference") -> str:
    """Référence lisible et unique (ex. NT-7K2M9QXA)."""
    while True:
        ref = f"{prefix}-" + "".join(secrets.choice(_ALPHABET) for _ in range(8))
        if not model.objects.filter(**{field: ref}).exists():
            return ref


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente de paiement"
        PAID = "paid", "Payée"
        FAILED = "failed", "Échouée"

    reference = models.CharField(max_length=20, unique=True, blank=True)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="orders")
    ticket_type = models.ForeignKey(TicketType, on_delete=models.PROTECT, related_name="orders")
    quantity = models.PositiveSmallIntegerField(default=1)
    unit_price = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    commission = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    # Réservation pour un ami (le ticket est émis à son nom)
    is_gift = models.BooleanField(default=False)
    recipient_first_name = models.CharField(max_length=100, blank=True)
    recipient_last_name = models.CharField(max_length=100, blank=True)
    recipient_email = models.EmailField(blank=True)
    recipient_phone = models.CharField(max_length=20, blank=True)
    recipient_sexe = models.CharField(max_length=1, blank=True)
    recipient_photo = models.ImageField(upload_to="tickets/photos/", blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = make_reference("CMD", Order)
        super().save(*args, **kwargs)

    @property
    def net_for_organizer(self):
        return self.total - self.commission

    @property
    def is_paid(self):
        return self.status == self.Status.PAID

    @property
    def is_upcoming(self):
        return not self.event.is_past


class Ticket(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tickets")
    reference = models.CharField(max_length=20, unique=True, blank=True)
    token = models.CharField(max_length=40, unique=True, blank=True, editable=False)
    holder_first_name = models.CharField(max_length=100)
    holder_last_name = models.CharField(max_length=100)
    holder_email = models.EmailField(blank=True)
    holder_phone = models.CharField(max_length=20, blank=True)
    holder_sexe = models.CharField(max_length=1, blank=True)
    holder_photo = models.ImageField(upload_to="tickets/photos/", blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = make_reference("NT", Ticket)
        if not self.token:
            self.token = secrets.token_urlsafe(18)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("tickets:detail", args=[self.reference])

    @property
    def event(self):
        return self.order.event

    @property
    def ticket_type(self):
        return self.order.ticket_type

    @property
    def holder_name(self):
        return f"{self.holder_first_name} {self.holder_last_name}".strip()

    @property
    def holder_sexe_label(self):
        return {"M": "Homme", "F": "Femme"}.get(self.holder_sexe, "—")

    @property
    def holder_phone_display(self):
        return format_phone(self.holder_phone) if self.holder_phone else ""

    @property
    def photo_file(self):
        """Photo du titulaire ; pour un achat personnel, repli sur la photo du profil."""
        if self.holder_photo:
            return self.holder_photo
        if not self.order.is_gift and self.order.buyer.photo:
            return self.order.buyer.photo
        return None

    @property
    def verify_path(self):
        return reverse("tickets:verify", args=[self.token])
