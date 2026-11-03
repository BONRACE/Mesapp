from django.contrib import admin

from .models import BusinessCard


@admin.register(BusinessCard)
class BusinessCardAdmin(admin.ModelAdmin):
    list_display = ("full_name", "company", "user", "is_active", "activated_at")
    list_filter = ("is_active", "theme")
    search_fields = ("full_name", "company", "user__email", "slug")
