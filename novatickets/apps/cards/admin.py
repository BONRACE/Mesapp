from django.contrib import admin

from .models import CarteVisite


@admin.register(CarteVisite)
class CarteVisiteAdmin(admin.ModelAdmin):
    list_display = ("nom_entreprise", "utilisateur", "theme", "paye", "cree_le")
    list_filter = ("theme", "paye")
