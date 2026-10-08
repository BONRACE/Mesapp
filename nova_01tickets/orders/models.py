import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse


def new_reference():
    return "NV-" + uuid.uuid4().hex[:8].upper()


class Order(models.Model):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    STATUSES = [(PENDING, "En attente"), (PAID, "Payé"), (FAILED, "Échoué")]

    reference = models.CharField(max_length=20, unique=True, default=new_reference)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="orders")
    ticket_type = models.ForeignKey("events.TicketType", on_delete=models.PROTECT, related_name="orders")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=0)
    total = models.DecimalField(max_digits=12, decimal_places=0)
    commission = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    net_amount = models.DecimalField("Net organisateur", max_digits=12, decimal_places=0, default=0)
    payment_method = models.CharField(max_length=60)
    payment_phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    def compute_amounts(self):
        self.unit_price = self.ticket_type.price
        self.total = self.unit_price * self.quantity
        rate = Decimal(str(settings.PLATFORM_COMMISSION_RATE))
        self.commission = (self.total * rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        self.net_amount = self.total - self.commission

    @property
    def is_paid(self):
        return self.status == self.PAID


class Ticket(models.Model):
    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tickets")
    number = models.PositiveIntegerField(default=1)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "number"]

    def __str__(self):
        return f"{self.order.reference}-{self.number}"

    @property
    def short_code(self):
        return str(self.code).split("-")[0].upper()

    def get_absolute_url(self):
        return reverse("orders:ticket", args=[self.code])

    def verify_url(self):
        return f"{settings.SITE_URL}{reverse('orders:verify', args=[self.code])}"


class Withdrawal(models.Model):
    PENDING = "pending"
    PAID = "paid"
    REJECTED = "rejected"
    STATUSES = [(PENDING, "En cours"), (PAID, "Versé"), (REJECTED, "Refusé")]

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="withdrawals")
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    method = models.CharField(max_length=60)
    phone = models.CharField(max_length=30)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Retrait {self.amount} – {self.organizer}"
