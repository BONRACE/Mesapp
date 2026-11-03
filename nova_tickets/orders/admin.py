from django.contrib import admin

from .models import Order, Ticket, Withdrawal


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "event", "buyer", "quantity", "total", "commission", "status", "paid_at")
    list_filter = ("status", "payment_method")
    search_fields = ("reference", "buyer__email", "event__name")
    inlines = [TicketInline]


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ("organizer", "amount", "method_label", "status", "created_at")
