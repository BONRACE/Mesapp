from django.contrib import admin

from .models import Payment, Withdrawal


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "user", "purpose", "amount", "method", "status", "created_at")
    list_filter = ("purpose", "status", "method")
    search_fields = ("reference", "user__email", "provider_reference")


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ("reference", "organizer", "amount", "method", "status", "created_at")
    list_filter = ("status", "method")
