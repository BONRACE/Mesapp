from django.contrib import admin

from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("reference", "user_email", "phone_number", "provider", "amount", "status", "created_at")
    list_filter = ("status", "provider")
    search_fields = ("reference", "user_email", "phone_number", "gateway_reference")
    # Journal de paiement : on ne modifie pas à la main les champs financiers.
    readonly_fields = [f.name for f in Transaction._meta.fields]

    def has_add_permission(self, request):
        return False
