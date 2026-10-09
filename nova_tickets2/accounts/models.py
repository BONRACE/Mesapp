from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Sum

from core.countries import get_country


class User(AbstractUser):
    SPECTATEUR = "spectateur"
    ORGANISATEUR = "organisateur"
    ROLES = [(SPECTATEUR, "Spectateur"), (ORGANISATEUR, "Organisateur")]
    SEXES = [("M", "Masculin"), ("F", "Féminin")]

    role = models.CharField(max_length=20, choices=ROLES, default=SPECTATEUR)
    country = models.CharField("Pays", max_length=2, default="BJ")
    phone = models.CharField("Téléphone", max_length=30)
    sexe = models.CharField(max_length=1, choices=SEXES, blank=True)
    profession = models.CharField(max_length=120, blank=True)
    photo = models.ImageField(upload_to="photos/", blank=True, null=True)

    # Organisateur
    org_name = models.CharField("Nom de l'organisation", max_length=150, blank=True)
    org_logo = models.ImageField(upload_to="org_logos/", blank=True, null=True)

    @property
    def is_organisateur(self):
        return self.role == self.ORGANISATEUR

    @property
    def is_spectateur(self):
        return self.role == self.SPECTATEUR

    @property
    def display_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def organizer_label(self):
        return self.org_name or self.display_name

    @property
    def country_info(self):
        return get_country(self.country)

    # --- Finances organisateur -------------------------------------------
    @property
    def gross_sales(self):
        from orders.models import Order
        agg = Order.objects.filter(event__organizer=self, status=Order.PAID).aggregate(t=Sum("total"))
        return agg["t"] or Decimal("0")

    @property
    def net_earnings(self):
        from orders.models import Order
        agg = Order.objects.filter(event__organizer=self, status=Order.PAID).aggregate(t=Sum("net_amount"))
        return agg["t"] or Decimal("0")

    @property
    def withdrawn(self):
        agg = self.withdrawals.exclude(status="rejected").aggregate(t=Sum("amount"))
        return agg["t"] or Decimal("0")

    @property
    def available_balance(self):
        return self.net_earnings - self.withdrawn
