import requests
import datetime
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- HELPER FUNCTION (Unchanged) ---
def _fetch_assignments_for_course(course, headers, base_url, status_callback):
    """
    Fetches all assignments from all buckets for a SINGLE course.
    This function is designed to be run in a separate thread.
    """
    course_id = course.get("id")
    course_name = course.get("name", "Unknown Course")
    if not course_id:
        return []

    if status_callback:
        status_callback(f"Starting fetch for course: {course_name}")

    assignments_for_course = []
    # These are the different assignment categories we want from Canvas
    buckets_to_fetch = ["past", "undated", "upcoming", "future", "ungraded"]

    for bucket in buckets_to_fetch:
        try:
            params = {"bucket": bucket, "per_page": 100}
            assignments_resp = requests.get(f"{base_url}/courses/{course_id}/assignments", headers=headers, params=params)
            assignments_resp.raise_for_status()
            
            # Add the course name to each assignment for later reference
            for assignment in assignments_resp.json():
                assignment['course_name'] = course_name
                assignments_for_course.append(assignment)

        except requests.exceptions.RequestException as e:
            if status_callback:
                status_callback(f"  -> Could not fetch bucket '{bucket}' for {course_name}: {e}")
    
    if status_callback:
        status_callback(f"Finished fetch for {course_name}, found {len(assignments_for_course)} raw assignments.")

    return assignments_for_course


# --- MAIN CANVAS FUNCTION (Unchanged) ---
def get_canvas_assignments(canvas_key, status_callback=None):
    """
    Fetch all relevant assignments from Canvas concurrently.
    - Fetches a list of courses.
    - Uses a ThreadPoolExecutor to fetch assignments for all courses in parallel.
    - De-duplicates the final list.
    """
    headers = {"Authorization": f"Bearer {canvas_key}"}
    base_url = "https://keyinstitute.instructure.com/api/v1"
    
    try:
        if status_callback:
            status_callback("Fetching courses from Canvas...")
        courses_resp = requests.get(f"{base_url}/courses", headers=headers, params={"enrollment_state": "active"})
        courses_resp.raise_for_status()
        courses = courses_resp.json()
        if status_callback:
            status_callback(f"Found {len(courses)} courses. Fetching assignments concurrently...")

        all_assignments_raw = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_course = {executor.submit(_fetch_assignments_for_course, course, headers, base_url, status_callback): course for course in courses}
            
            for future in as_completed(future_to_course):
                try:
                    assignments_from_course = future.result()
                    all_assignments_raw.extend(assignments_from_course)
                except Exception as exc:
                    course_name = future_to_course[future].get('name', 'Unknown')
                    if status_callback:
                        status_callback(f"'{course_name}' generated an exception: {exc}")

        if status_callback:
            status_callback("All courses processed. De-duplicating assignments...")

        final_assignments = []
        fetched_assignment_ids = set()
        for assignment in all_assignments_raw:
            if assignment['id'] not in fetched_assignment_ids:
                final_assignments.append({
                    "name": assignment.get("name", "Unnamed Assignment"),
                    "due_at": assignment.get("due_at"),
                    "lock_at": assignment.get("lock_at"),
                    "created_at": assignment.get("created_at"),
                    "description": assignment.get("description", ""),
                    "html_url": assignment.get("html_url", ""),
                    "course_name": assignment.get("course_name", "Unknown Course")
                })
                fetched_assignment_ids.add(assignment['id'])

        if status_callback:
            status_callback(f"Total unique assignments fetched: {len(final_assignments)}")
        
        return final_assignments

    except Exception as e:
        if status_callback:
            status_callback(f"A critical error occurred while fetching from Canvas: {e}")
        else:
            raise
        return []


# --- NOTION FUNCTIONS ---

def _get_all_notion_pages_paginated(database_id, headers, status_callback=None):
    """
    Gets all pages from the database, handling pagination.
    Uses the stable 2022-06-28 API version.
    """
    pages_map = {}
    next_cursor = None
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    while True:
        # This payload is correct for the 2022-06-28 API version
        payload = {"start_cursor": next_cursor} if next_cursor else {}
            
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            for page in data.get("results", []):
                try:
                    title_property = page.get("properties", {}).get("Name", {}).get("title", [])
                    if title_property:
                        page_title = title_property[0].get("plain_text")
                        page_id = page.get("id")
                        if page_title and page_id:
                            pages_map[page_title] = page_id
                except (IndexError, KeyError):
                    continue
            if data.get("has_more"):
                next_cursor = data.get("next_cursor")
            else:
                break
        except requests.exceptions.RequestException as e:
            if status_callback:
                status_callback(f"⚠️ Error fetching Notion pages: {e}")
            return None
    return pages_map

# --- NEW: Moved truncate_text to be a global helper ---
def truncate_text(text):
    max_length = 2000
    if not text:
        return ""
    return text[:max_length - 3] + "..." if len(text) > max_length else text

# --- NEW: Helper function to update page content ---
def _update_page_content(page_id, new_content, headers, status_callback=None):
    """
    Deletes all existing content (child blocks) from a page and adds new content.
    This is a DESTRUCTIVE operation.
    """
    try:
        blocks_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
        
        # 1. Get all existing blocks
        get_resp = requests.get(blocks_url, headers=headers)
        
        results = []
        if get_resp.ok:
            results = get_resp.json().get("results", [])
        elif get_resp.status_code == 404:
            pass # Page has no children, which is fine. We will add content in step 3.
        else:
            get_resp.raise_for_status() # Raise for other errors
        
        # 2. Delete all existing blocks (sequentially)
        for block in results:
            block_id = block.get("id")
            if block_id:
                delete_url = f"https://api.notion.com/v1/blocks/{block_id}"
                del_resp = requests.delete(delete_url, headers=headers)
                if not del_resp.ok:
                    if status_callback: status_callback(f"  -> ⚠️ Could not delete block {block_id}: {del_resp.text}")
        
        # 3. Add the new content
        if new_content:
            new_block_data = {
                "children": [{
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": new_content}}]}
                }]
            }
            patch_resp = requests.patch(blocks_url, headers=headers, json=new_block_data)
            patch_resp.raise_for_status()
            
    except requests.exceptions.RequestException as e:
        if status_callback:
            status_callback(f"  -> ⚠️ Failed to update content for page {page_id}: {e}")
# --- END OF NEW HELPER ---


# --- MODIFIED: Accepts date_property_name and is_first_sync ---
def add_to_notion(notion_key, database_id, assignments, status_callback, date_property_name, is_first_sync=False):
    """
    Adds/updates Canvas assignments in Notion.
    - is_first_sync=True: Skips 2-week check and force-updates content.
    - is_first_sync=False: Enables 2-week check and does NOT update content.
    """
    notion_api_url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {notion_key}",
        "Notion-Version": "2022-06-28", # Using stable version
        "Content-Type": "application/json"
    }
    database_id = database_id.strip()

    if status_callback:
        status_callback("Fetching existing entries from Notion to prevent duplicate checks...")
    
    existing_pages_map = _get_all_notion_pages_paginated(database_id, headers, status_callback)
    
    if existing_pages_map is None:
        if status_callback:
             status_callback("❌ Could not pre-fetch Notion pages. Aborting sync.")
        raise Exception("Could not pre-fetch Notion pages. Aborting sync.")
    
    if status_callback:
        status_callback(f"Found {len(existing_pages_map)} existing entries in Notion.")
        if is_first_sync:
            status_callback("   Running FIRST SYNC: Will update all entries and descriptions.")
        else:
            status_callback("   Running subsequent sync: Will skip old entries and preserve descriptions.")


    today = datetime.date.today()
    two_weeks_ago = today - datetime.timedelta(weeks=2)

    for idx, assignment in enumerate(assignments, start=1):
        try:
            assignment_name = assignment.get("name", "Unnamed Assignment")
            if status_callback:
                status_callback(f"Processing {idx}/{len(assignments)}: {assignment_name}")
            
            raw_description = assignment.get("description", "") or ""
            plain_description = re.sub(r'<[^>]+>', '', raw_description).strip()
            
            # --- MODIFICATION: Get description content early ---
            description_content = truncate_text(plain_description)

            # --- MODIFICATION: Chained date logic ---
            date_to_use_str = assignment.get("due_at") or assignment.get("lock_at") or assignment.get("created_at")
            
            due_date_iso = None
            if date_to_use_str:
                try:
                    date_datetime = datetime.datetime.fromisoformat(date_to_use_str.replace("Z", "+00:00"))
                    due_date_iso = date_datetime.date().isoformat()
                except (ValueError, TypeError):
                    pass 
            
            course_name = assignment.get("course_name", "")
            url = assignment.get("html_url", "")
            
            properties = {
                "Name": {"title": [{"text": {"content": assignment_name}}]},
                date_property_name: {"date": {"start": due_date_iso} if due_date_iso else None}
            }
            
            if course_name:
                properties["Course"] = {"rich_text": [{"text": {"content": course_name}}]}
            if url:
                properties["URL"] = {"url": url} 
            
            existing_page_id = existing_pages_map.get(assignment_name)
            
            if existing_page_id:
                # This assignment already exists in Notion.
                
                # --- MODIFICATION: 2-week check is now conditional ---
                if not is_first_sync: # Only run check if NOT the first sync
                    if due_date_iso:
                        assignment_date = datetime.date.fromisoformat(due_date_iso)
                        if assignment_date < two_weeks_ago:
                            if status_callback: status_callback(f"Skipping update (overdue > 2 weeks): {assignment_name}")
                            continue # Skip this assignment
                
                if status_callback: status_callback(f"Updating existing assignment: {assignment_name}")
                update_url = f"https://api.notion.com/v1/pages/{existing_page_id}"
                update_payload = {"properties": properties} 
                update_resp = requests.patch(update_url, headers=headers, json=update_payload)
                
                # --- MODIFIED: Content update is now conditional ---
                if update_resp.ok:
                    if status_callback: status_callback(f"🔄 Updated properties for '{assignment_name}'.")
                    
                    # Only update content on the first sync
                    if is_first_sync:
                        if status_callback: status_callback(f"  -> First sync: Updating content for '{assignment_name}'...")
                        _update_page_content(existing_page_id, description_content, headers, status_callback)
                        if status_callback: status_callback(f"🔄 Updated content for '{assignment_name}'.")
                else:
                    if status_callback: status_callback(f"⚠️ Failed to update '{assignment_name}': {update_resp.text}")
                
                continue 
            
            # If we are here, it's a new assignment. Create it.
            page_data = {"parent": {"database_id": database_id}, "properties": properties}
            
            if description_content:
                page_data["children"] = [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"text": {"content": description_content}}]}}]
            
            response = requests.post(notion_api_url, headers=headers, json=page_data)
            
            if response.ok:
                if status_callback: status_callback(f"✅ Added '{assignment_name}' to Notion.")
            else:
                 if status_callback:
                    error_details = response.json()
                    status_callback(f"⚠️ Error adding '{assignment_name}': {json.dumps(error_details, indent=2)}")
        
        except Exception as e:
            if status_callback: status_callback(f"❌ Unhandled error with '{assignment.get('name', 'Unnamed Assignment')}': {e}")

# --- FIX: This function now finds the date property and returns its name ---
def ensure_database_properties(notion_key, database_id, status_callback=None):
    """
    Checks a Notion database for required properties.
    - Finds the *first* existing date property.
    - If no date property exists, creates one named 'Due Date'.
    - Creates 'Course' and 'URL' properties if they are missing.
    - Renames the title property to 'Name' if it's not already.
    Returns (True, date_property_name) on success, (False, None) on failure.
    """
    if status_callback:
        status_callback("Checking Notion database schema...")

    headers = {
        "Authorization": f"Bearer {notion_key}",
        "Notion-Version": "2022-06-28", # Using stable version
        "Content-Type": "application/json"
    }
    db_url = f"https://api.notion.com/v1/databases/{database_id}"

    # 1. Get the current database schema
    try:
        response = requests.get(db_url, headers=headers)
        response.raise_for_status()
        schema = response.json()
    except requests.exceptions.RequestException as e:
        if status_callback:
            status_callback(f"❌ ERROR: Could not fetch database schema. Check Database ID and API key.")
            status_callback(f"   Details: {e}")
        return False, None # Return tuple

    current_properties = schema.get("properties", {})
    existing_names = list(current_properties.keys())
    properties_to_update = {}
    title_property_current_name = None
    
    # --- FIX: Find the first available date property ---
    date_property_name = None
    for name, details in current_properties.items():
        if details.get("type") == "date":
            date_property_name = name # Found it!
            if status_callback:
                status_callback(f"   Found existing date property: '{name}'")
            break
            
    # 2. Find the 'title' property and check if it needs renaming
    for name, details in current_properties.items():
        if details.get("type") == "title":
            title_property_current_name = name
            break
    
    if title_property_current_name and title_property_current_name != "Name":
        if status_callback:
            status_callback(f"Renaming title property from '{title_property_current_name}' to 'Name'...")
        properties_to_update[title_property_current_name] = {"name": "Name"}
        existing_names.remove(title_property_current_name)
        existing_names.append("Name")

    # 3. Define *other* required properties
    required_props = {
        "Course": {"rich_text": {}},
        "URL": {"url": {}}
    }
    for req_name, req_payload in required_props.items():
        if req_name not in existing_names:
            if status_callback:
                status_callback(f"Adding missing property: '{req_name}'...")
            properties_to_update[req_name] = req_payload
            
    # 4. If we didn't find a date property, create one
    if not date_property_name:
        if status_callback:
            status_callback("   No date property found. Creating new 'Due Date' property...")
        properties_to_update["Due Date"] = {"date": {}}
        date_property_name = "Due Date" # This will be our new date property

    # 5. If we have changes, send the PATCH request
    if not properties_to_update:
        if status_callback:
            status_callback("✅ Database schema is correct. No changes needed.")
        return True, date_property_name # Return tuple

    patch_payload = {"properties": properties_to_update}
    try:
        patch_resp = requests.patch(db_url, headers=headers, json=patch_payload)
        patch_resp.raise_for_status()
        if status_callback:
            status_callback("✅ Database schema successfully updated!")
        return True, date_property_name # Return tuple
    except requests.exceptions.RequestException as e:
        if status_callback:
            status_callback(f"❌ ERROR: Failed to update database properties: {e.text}")
            status_callback("   Please ensure your Notion integration has 'Update database properties' permissions.")
        return False, None # Return tuple