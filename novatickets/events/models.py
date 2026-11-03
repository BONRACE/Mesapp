from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone


class Event(models.Model):
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    name = models.CharField("Nom de l'événement", max_length=200)
    description = models.TextField("Description", blank=True)
    location = models.CharField("Lieu", max_length=200)
    visual = models.ImageField("Visuel de l'événement", upload_to="events/visuals/")
    logo = models.ImageField("Logo de l'événement", upload_to="events/logos/", blank=True, null=True)
    start_date = models.DateField("Date de début")
    end_date = models.DateField("Date de fin")
    start_time = models.TimeField("Heure de début")
    purchase_deadline = models.DateField("Date limite d'achat")
    is_published = models.BooleanField("Publié", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date", "start_time"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.pk])

    @property
    def is_past(self):
        return self.end_date < timezone.localdate()

    @property
    def sales_closed(self):
        return self.purchase_deadline < timezone.localdate() or self.is_past

    @property
    def total_stock(self):
        return self.ticket_types.aggregate(s=Sum("stock"))["s"] or 0

    @property
    def tickets_sold(self):
        return self.orders.filter(status="paid").aggregate(s=Sum("quantity"))["s"] or 0

    @property
    def sold_out(self):
        return self.total_stock > 0 and self.tickets_sold >= self.total_stock

    @property
    def min_price(self):
        first = self.ticket_types.order_by("price").first()
        return first.price if first else None

    @property
    def gross_revenue(self):
        return self.orders.filter(status="paid").aggregate(s=Sum("total"))["s"] or 0

    @property
    def net_revenue(self):
        return self.orders.filter(status="paid").aggregate(s=Sum("organizer_amount"))["s"] or 0

    @property
    def logo_or_none(self):
        return self.logo or self.organizer.org_logo or None


class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField("Type de ticket", max_length=80)
    price = models.PositiveIntegerField("Prix (FCFA)")
    stock = models.PositiveIntegerField("Stock")

    class Meta:
        ordering = ["price", "id"]

    def __str__(self):
        return f"{self.name} — {self.event.name}"

    @property
    def sold(self):
        return self.orders.filter(status="paid").aggregate(s=Sum("quantity"))["s"] or 0

    @property
    def remaining(self):
        return max(self.stock - self.sold, 0)
