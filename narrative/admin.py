from django.contrib import admin
from .models import EngagementSignal


@admin.register(EngagementSignal)
class EngagementSignalAdmin(admin.ModelAdmin):
    list_display = ['series_slug', 'action', 'created_at', 'metadata']
    list_filter = ['action', 'series_slug', 'created_at']
    readonly_fields = ['series_slug', 'action', 'created_at', 'metadata']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
