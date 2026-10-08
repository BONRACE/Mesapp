from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PAID = "paid", "Payée"

    reference = models.CharField(max_length=20, unique=True)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    event = models.ForeignKey("events.Event", on_delete=models.PROTECT, related_name="orders")
    ticket_type = models.ForeignKey("events.TicketType", on_delete=models.PROTECT, related_name="orders")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    commission = models.PositiveIntegerField(default=0)         # part de la plateforme
    organizer_amount = models.PositiveIntegerField(default=0)   # part reversée à l'organisateur
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    payment_method = models.CharField(max_length=30, blank=True)
    payment_label = models.CharField(max_length=60, blank=True)
    payment_phone = models.CharField(max_length=20, blank=True)
    payment_ref = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} — {self.event.name}"


class Ticket(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tickets")
    reference = models.CharField(max_length=24, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def event(self):
        return self.order.event

    @property
    def holder(self):
        return self.order.buyer

    def __str__(self):
        return self.reference


class Withdrawal(models.Model):
    class Status(models.TextChoices):
        COMPLETED = "completed", "Effectué"

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="withdrawals")
    amount = models.PositiveIntegerField()
    method = models.CharField(max_length=30)
    method_label = models.CharField(max_length=60)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.COMPLETED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Retrait {self.amount} — {self.organizer}"
