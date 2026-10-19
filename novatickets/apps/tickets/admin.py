from django.contrib import admin

from .models import Commande, Ticket


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = ("reference", "prix_unitaire", "commission", "montant_net_organisateur")


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ("reference", "acheteur", "total", "statut", "creee_le")
    list_filter = ("statut",)
    inlines = [TicketInline]
