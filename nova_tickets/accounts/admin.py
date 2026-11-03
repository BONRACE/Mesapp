from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class NovaUserAdmin(UserAdmin):
    list_display = ("email", "first_name", "last_name", "role", "country", "phone")
    list_filter = ("role", "country", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone", "org_name")
    fieldsets = UserAdmin.fieldsets + (
        ("NovaTickets", {"fields": ("role", "country", "phone", "sexe", "profession", "photo", "org_name", "org_logo")}),
    )
