from django.contrib import admin

from .models import Order, Ticket


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    readonly_fields = ("reference", "token")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "buyer", "event", "ticket_type", "quantity", "total", "commission", "status", "is_gift")
    list_filter = ("status", "is_gift")
    search_fields = ("reference", "buyer__email", "event__name")
    inlines = [TicketInline]


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "holder_last_name", "holder_first_name", "order", "used_at")
    search_fields = ("reference", "holder_last_name", "holder_email")
