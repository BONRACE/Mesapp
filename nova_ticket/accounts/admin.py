from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PlanAbonnement


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


@admin.register(PlanAbonnement)
class PlanAbonnementAdmin(admin.ModelAdmin):
    list_display = ("organisateur", "plan", "statut", "date_expiration", "est_pro_actif")
    list_filter = ("plan", "statut")
    search_fields = ("organisateur__username", "organisateur__nom", "organisateur__nom_structure")
    readonly_fields = ("date_debut",)

    @admin.display(boolean=True, description="Pro actif")
    def est_pro_actif(self, obj):
        return obj.est_pro_actif()
