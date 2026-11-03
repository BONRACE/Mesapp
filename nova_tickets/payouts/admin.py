from django.contrib import admin

from .models import PayoutMethod


@admin.register(PayoutMethod)
class PayoutMethodAdmin(admin.ModelAdmin):
    list_display = ("organizer", "kind", "account_holder", "display_account", "is_default")
    list_filter = ("kind", "is_default")
    search_fields = ("organizer__email", "account_holder", "account_number")
