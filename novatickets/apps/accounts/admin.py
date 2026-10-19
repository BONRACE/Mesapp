from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import ProfilOrganisateur, User


@admin.register(User)
class NovaUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("NovaTickets", {"fields": ("role", "sexe", "profession", "photo", "pays", "indicatif", "telephone")}),
    )
    list_display = ("email", "nom_complet", "role", "pays", "telephone", "is_active")
    list_filter = ("role", "pays", "is_active")
    search_fields = ("email", "first_name", "last_name", "telephone")


@admin.register(ProfilOrganisateur)
class ProfilOrganisateurAdmin(admin.ModelAdmin):
    list_display = ("structure", "utilisateur", "verifie")
    list_filter = ("verifie",)
    list_editable = ("verifie",)
