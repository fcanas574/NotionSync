from django.contrib import admin
from .models import UserProfile, SyncLog


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at', 'first_sync_complete']
    search_fields = ['user__username', 'user__email']
    list_filter = ['first_sync_complete', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Canvas Credentials', {
            'fields': ('canvas_api_key', 'use_default_canvas_url', 'canvas_base_url')
        }),
        ('Notion Credentials', {
            'fields': ('notion_api_key', 'notion_database_id')
        }),
        ('Sync Settings', {
            'fields': ('selected_course_ids', 'sync_buckets', 'sync_time', 'first_sync_complete')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'started_at', 'status', 'assignments_synced']
    list_filter = ['status', 'started_at']
    search_fields = ['user__username', 'message']
    readonly_fields = ['started_at', 'completed_at']
    date_hierarchy = 'started_at'
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Sync Info', {
            'fields': ('started_at', 'completed_at', 'status', 'assignments_synced')
        }),
        ('Details', {
            'fields': ('message',)
        }),
    )
