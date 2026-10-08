from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Event(models.Model):
    DRAFT = "draft"
    PUBLISHED = "published"
    STATUSES = [(DRAFT, "Brouillon"), (PUBLISHED, "Publié")]

    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    name = models.CharField("Nom de l'événement", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    location = models.CharField("Lieu", max_length=200, blank=True)
    banner = models.ImageField("Visuel", upload_to="events/", blank=True, null=True)
    logo = models.ImageField("Logo de l'événement", upload_to="event_logos/", blank=True, null=True)
    start_date = models.DateField("Date de début")
    end_date = models.DateField("Date de fin")
    start_time = models.TimeField("Heure de début")
    sales_deadline = models.DateField("Date limite d'achat")
    status = models.CharField(max_length=12, choices=STATUSES, default=DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date", "start_time"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:200] or "evenement"
            slug, i = base, 2
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.slug])

    @property
    def is_published(self):
        return self.status == self.PUBLISHED

    @property
    def sales_open(self):
        return self.is_published and timezone.localdate() <= self.sales_deadline

    @property
    def is_past(self):
        return self.end_date < timezone.localdate()

    @property
    def min_price(self):
        prices = [t.price for t in self.ticket_types.all()]
        return min(prices) if prices else None

    @property
    def tickets_sold(self):
        from orders.models import Order
        return Order.objects.filter(event=self, status=Order.PAID).aggregate(t=Sum("quantity"))["t"] or 0

    @property
    def revenue(self):
        from orders.models import Order
        return Order.objects.filter(event=self, status=Order.PAID).aggregate(t=Sum("net_amount"))["t"] or 0


class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField("Type de ticket", max_length=80)
    price = models.DecimalField("Prix (FCFA)", max_digits=10, decimal_places=0)
    stock = models.PositiveIntegerField("Quantité disponible", default=100)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} – {self.event.name}"

    @property
    def sold(self):
        from orders.models import Order
        return Order.objects.filter(ticket_type=self, status=Order.PAID).aggregate(t=Sum("quantity"))["t"] or 0

    @property
    def remaining(self):
        return max(self.stock - self.sold, 0)
