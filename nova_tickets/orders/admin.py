from django.contrib import admin

from .models import Order, Ticket, Withdrawal


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "event", "quantity", "total", "commission", "status")
    list_filter = ("status", "payment_method")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("code", "order", "number", "used")


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ("organizer", "amount", "method", "phone", "status", "created_at")
    list_filter = ("status",)
    list_editable = ("status",)
