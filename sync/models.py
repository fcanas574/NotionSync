from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re


def validate_notion_db_id(value):
    """Validate that Notion database ID is 32 hex characters."""
    if value and not re.fullmatch(r'[a-f0-9]{32}', value.lower()):
        raise ValidationError(
            'Notion Database ID must be exactly 32 hexadecimal characters'
        )


class UserProfile(models.Model):
    """
    User profile to store Canvas and Notion API credentials.
    Replaces the local keyring storage from the desktop app.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Canvas credentials
    # NOTE: API keys stored in plain text for simplicity. For production,
    # consider using django-fernet-fields or similar encryption library.
    canvas_api_key = models.CharField(max_length=255, blank=True, help_text="Canvas API Key")
    canvas_base_url = models.URLField(
        max_length=255, 
        default="https://keyinstitute.instructure.com/api/v1",
        help_text="Canvas API Base URL"
    )
    use_default_canvas_url = models.BooleanField(default=True)
    
    # Notion credentials
    # NOTE: API keys stored in plain text for simplicity. For production,
    # consider using django-fernet-fields or similar encryption library.
    notion_api_key = models.CharField(max_length=255, blank=True, help_text="Notion API Key")
    notion_database_id = models.CharField(
        max_length=32, 
        blank=True, 
        validators=[validate_notion_db_id],
        help_text="Notion Database ID (32 char hex)"
    )
    
    # Sync settings
    selected_course_ids = models.JSONField(default=list, blank=True, help_text="List of selected Canvas course IDs")
    sync_buckets = models.JSONField(
        default=list,
        blank=True,
        help_text="Canvas assignment buckets to sync (past, undated, upcoming, future, ungraded)"
    )
    sync_time = models.TimeField(null=True, blank=True, help_text="Scheduled daily sync time")
    
    # Tracking
    first_sync_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile for {self.user.username}"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class SyncLog(models.Model):
    """
    Log of sync operations for tracking history and debugging.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sync_logs')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('running', 'Running'),
            ('success', 'Success'),
            ('failed', 'Failed'),
        ],
        default='running'
    )
    message = models.TextField(blank=True)
    assignments_synced = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Sync by {self.user.username} at {self.started_at} - {self.status}"
    
    class Meta:
        ordering = ['-started_at']
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"
