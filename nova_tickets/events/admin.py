from django.contrib import admin

from .models import Event, TicketType


class TicketTypeInline(admin.TabularInline):
    model = TicketType
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "organizer", "start_date", "is_published")
    list_filter = ("is_published",)
    search_fields = ("name", "organizer__email", "organizer__org_name")
    inlines = [TicketTypeInline]
