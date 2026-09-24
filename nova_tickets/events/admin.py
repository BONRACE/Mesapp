from django.contrib import admin
from .models import Event, TicketType


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("nom", "organisateur", "date_debut", "statut", "billets_vendus")
    inlines = [TicketTypeInline]


admin.site.register(TicketType)
