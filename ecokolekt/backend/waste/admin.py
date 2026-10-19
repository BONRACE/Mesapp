from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import CollectionPoint, PickupRequest, WasteCategory

admin.site.register(WasteCategory)
admin.site.register(CollectionPoint, GISModelAdmin)


@admin.register(PickupRequest)
class PickupAdmin(GISModelAdmin):
    list_display = ("id", "citizen", "collector", "category", "status", "created_at")
    list_filter = ("status", "category")
