from django.contrib import admin

from .models import Evenement, TypeTicket


class TypeTicketInline(admin.TabularInline):
    model = TypeTicket
    extra = 0


@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisateur", "date_debut", "statut")
    list_filter = ("statut", "ville")
    search_fields = ("nom", "ville")
    inlines = [TypeTicketInline]
