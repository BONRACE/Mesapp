from django.contrib import admin

from .models import ScanLog


@admin.register(ScanLog)
class ScanLogAdmin(admin.ModelAdmin):
    list_display = ("scanned_at", "event", "result", "code", "source", "scanned_by")
    list_filter = ("result", "source", "event")
    readonly_fields = [f.name for f in ScanLog._meta.fields]
