from django.contrib import admin

from .models import OTPCode, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "full_name", "role", "is_onboarded", "is_active")
    list_filter = ("role", "is_onboarded", "is_active")
    search_fields = ("phone_number", "full_name", "organization")
    exclude = ("password",)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ("phone_number", "created_at", "expires_at", "attempts", "consumed")
    readonly_fields = ("code_hash",)
