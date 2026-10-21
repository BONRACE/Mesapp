from django.contrib import admin

from .models import BusinessCard


@admin.register(BusinessCard)
class BusinessCardAdmin(admin.ModelAdmin):
    list_display = ("company_name", "contact_name", "theme", "owner", "is_paid", "created_at")
    list_filter = ("theme", "is_paid")
    search_fields = ("company_name", "contact_name", "owner__email")
