from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import CollectorProfile, OTPCode, RecyclerProfile, User


@admin.register(User)
class UserAdmin(GISModelAdmin):
    list_display = ("phone", "full_name", "role", "is_approved", "eco_points", "date_joined")
    list_filter = ("role", "is_approved")
    search_fields = ("phone", "full_name")


admin.site.register(CollectorProfile, GISModelAdmin)
admin.site.register(RecyclerProfile)
admin.site.register(OTPCode)
