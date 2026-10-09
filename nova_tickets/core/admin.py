from django.contrib import admin

from .models import BusinessCard


@admin.register(BusinessCard)
class BusinessCardAdmin(admin.ModelAdmin):
    list_display = ("company_name", "contact_name", "user", "updated_at")
