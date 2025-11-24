"""
Services layer for Canvas and Notion sync operations.
Extracted from PyQt6 GUI code to be framework-agnostic.
"""
from canvas_notion_calendar_db_v1 import (
    get_canvas_assignments,
    add_to_notion,
    ensure_database_properties,
    get_canvas_courses,
)


class SyncService:
    """
    Service for handling Canvas to Notion synchronization.
    """
    
    @staticmethod
    def sync_assignments(canvas_key, notion_key, notion_db_id, base_url, buckets, 
                        selected_course_ids=None, is_first_sync=False, status_callback=None):
        """
        Sync Canvas assignments to Notion database.
        
        Args:
            canvas_key: Canvas API key
            notion_key: Notion API key
            notion_db_id: Notion database ID
            base_url: Canvas API base URL
            buckets: List of assignment buckets to sync
            selected_course_ids: Optional list of course IDs to filter
            is_first_sync: Whether this is the first sync
            status_callback: Optional callback function for status updates
            
        Returns:
            tuple: (success: bool, message: str, assignments_count: int)
        """
        try:
            if status_callback:
                status_callback("Verifying Notion database properties...")
            
            schema_ok, date_property_name = ensure_database_properties(
                notion_key, notion_db_id, status_callback
            )
            
            if not schema_ok:
                return False, "Database setup failed. Check permissions and Database ID.", 0
            
            if status_callback:
                status_callback(f"Using date property: '{date_property_name}'")
                status_callback("Fetching assignments from Canvas...")
            
            assignments = get_canvas_assignments(
                canvas_key, base_url, buckets, selected_course_ids, status_callback
            )
            
            if not assignments:
                return True, "No assignments found or Canvas fetch failed.", 0
            
            if status_callback:
                status_callback(f"Adding {len(assignments)} assignments to Notion...")
            
            add_to_notion(
                notion_key,
                notion_db_id,
                assignments,
                status_callback,
                date_property_name,
                is_first_sync=is_first_sync
            )
            
            return True, f"Successfully synced {len(assignments)} assignments.", len(assignments)
            
        except Exception as e:
            return False, f"Sync error: {str(e)}", 0
    
    @staticmethod
    def get_courses(canvas_key, base_url):
        """
        Fetch list of courses from Canvas.
        
        Args:
            canvas_key: Canvas API key
            base_url: Canvas API base URL
            
        Returns:
            list: List of course dictionaries
        """
        try:
            return get_canvas_courses(canvas_key, base_url)
        except Exception:
            return []
