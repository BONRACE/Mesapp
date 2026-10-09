from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class NovaUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("NovaTickets", {"fields": ("role", "country", "phone", "sexe", "profession", "photo", "org_name", "org_logo")}),
    )
    list_display = ("username", "email", "role", "country", "phone")
    list_filter = ("role", "country")
