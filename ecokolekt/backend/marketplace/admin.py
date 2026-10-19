from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import Listing, Order


@admin.register(Listing)
class ListingAdmin(GISModelAdmin):
    list_display = ("title", "seller", "category", "quantity_kg", "unit_price", "is_active")
    list_filter = ("category", "is_active", "grade")
    search_fields = ("title", "seller__phone", "seller__full_name")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "buyer", "seller", "listing", "quantity_kg", "total", "commission", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = ("created_at", "paid_at", "shipped_at", "delivered_at")
