from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "payer", "provider", "method", "amount", "status", "needs_refund", "created_at")
    list_filter = ("status", "provider", "needs_refund")
    readonly_fields = ("created_at", "updated_at")
