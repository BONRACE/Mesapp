from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Event(models.Model):
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    name = models.CharField("nom de l'événement", max_length=160)
    slug = models.SlugField(max_length=190, unique=True, blank=True)
    description = models.TextField(blank=True)
    visual = models.ImageField("visuel", upload_to="evenements/visuels/")
    logo = models.ImageField("logo", upload_to="evenements/logos/", blank=True)
    venue = models.CharField("lieu", max_length=200, blank=True)
    city = models.CharField("ville", max_length=100, blank=True)
    start_date = models.DateField("date de début")
    end_date = models.DateField("date de fin")
    start_time = models.TimeField("heure de début")
    sales_deadline = models.DateTimeField("date limite d'achat")
    is_published = models.BooleanField("publié", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date", "start_time"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:150] or "evenement"
            slug, n = base, 2
            while Event.objects.filter(slug=slug).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.slug])

    @property
    def sales_open(self):
        return self.is_published and timezone.now() <= self.sales_deadline and self.end_date >= timezone.localdate()

    @property
    def is_past(self):
        return self.end_date < timezone.localdate()

    @property
    def min_price(self):
        prices = [t.price for t in self.ticket_types.all()]
        return min(prices) if prices else None

    @property
    def tickets_sold(self):
        return self.ticket_types.aggregate(s=Sum("sold"))["s"] or 0

    @property
    def total_stock(self):
        return self.ticket_types.aggregate(s=Sum("stock"))["s"] or 0


class TicketType(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField("type de ticket", max_length=80)
    price = models.PositiveIntegerField("prix (FCFA)", help_text="0 pour un ticket gratuit")
    stock = models.PositiveIntegerField("stock")
    sold = models.PositiveIntegerField("vendus", default=0, editable=False)

    class Meta:
        ordering = ["price", "id"]

    def __str__(self):
        return f"{self.name} — {self.event.name}"

    @property
    def remaining(self):
        return max(self.stock - self.sold, 0)

    @property
    def sold_out(self):
        return self.remaining == 0
