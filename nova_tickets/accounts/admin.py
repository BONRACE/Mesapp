from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "nom_complet", "role", "email", "is_active")
    list_filter = ("role", "sexe")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Profil NovaTickets", {
            "fields": ("role", "nom", "prenoms", "sexe", "profession", "photo",
                       "telephone", "nom_structure", "logo_organisateur")
        }),
    )
