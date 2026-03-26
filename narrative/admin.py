from django.contrib import admin
from .models import AgentMiss, EngagementSignal


@admin.register(AgentMiss)
class AgentMissAdmin(admin.ModelAdmin):
    list_display = ['path', 'user_agent_short', 'created_at']
    list_filter = ['created_at']
    search_fields = ['path', 'user_agent']
    readonly_fields = ['path', 'user_agent', 'referer', 'created_at']
    ordering = ['-created_at']

    def user_agent_short(self, obj):
        return obj.user_agent[:80] + ('...' if len(obj.user_agent) > 80 else '')
    user_agent_short.short_description = 'User Agent'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


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
