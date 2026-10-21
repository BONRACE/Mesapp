from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class NovaUserAdmin(UserAdmin):
    list_display = ("email", "last_name", "first_name", "role", "country", "phone", "is_active")
    list_filter = ("role", "country", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name", "phone", "organisation_name")
    ordering = ("email",)
    fieldsets = UserAdmin.fieldsets + (
        ("NovaTickets", {"fields": ("role", "country", "phone", "sexe", "profession", "photo",
                                    "organisation_name", "organisation_logo")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "username", "password1", "password2", "role")}),
    )
