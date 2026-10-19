from django.contrib import admin

from .models import BusinessCard, CardPayment


@admin.register(BusinessCard)
class BusinessCardAdmin(admin.ModelAdmin):
    list_display = ("company_name", "contact_name", "user", "template", "paid_at", "updated_at")
    list_filter = ("template",)


@admin.register(CardPayment)
class CardPaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "card", "user", "amount", "method", "status", "created_at")
    list_filter = ("status",)
