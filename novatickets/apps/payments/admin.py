from django.contrib import admin

from .models import Paiement, Retrait


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("reference", "utilisateur", "objet", "montant", "fournisseur", "statut", "cree_le")
    list_filter = ("statut", "objet", "fournisseur")
    search_fields = ("reference", "reference_externe")


@admin.register(Retrait)
class RetraitAdmin(admin.ModelAdmin):
    list_display = ("reference", "organisateur", "montant", "moyen", "statut", "demande_le")
    list_filter = ("statut", "moyen")
    list_editable = ("statut",)
