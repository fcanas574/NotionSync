import requests
import datetime
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- NEW HELPER FUNCTION FOR CONCURRENT FETCHING ---
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


# --- REFACTORED MAIN FUNCTION TO USE THE HELPER ---
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
        # Use a ThreadPoolExecutor to run our helper function for each course in parallel
        # max_workers can be adjusted, but 10 is a safe default for I/O tasks
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Create a "future" for each course fetching task
            future_to_course = {executor.submit(_fetch_assignments_for_course, course, headers, base_url, status_callback): course for course in courses}
            
            # As each future completes, process its result
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

        # --- De-duplication Step (after all threads are done) ---
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


# --- This function for Notion sync remains unchanged ---
def _get_all_notion_pages_paginated(database_id, headers, status_callback=None):
    pages_map = {}
    next_cursor = None
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    while True:
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

def add_to_notion(notion_key, database_id, assignments, status_callback=None):
    notion_api_url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {notion_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    database_id = database_id.strip()

    if status_callback:
        status_callback("Fetching existing entries from Notion to prevent duplicate checks...")
    existing_pages_map = _get_all_notion_pages_paginated(database_id, headers, status_callback)
    
    if existing_pages_map is None:
        if status_callback:
            status_callback("❌ Could not pre-fetch Notion pages. Aborting sync.")
        return
    if status_callback:
        status_callback(f"Found {len(existing_pages_map)} existing entries in Notion.")

    def truncate_text(text):
        max_length = 2000
        if not text:
            return ""
        return text[:max_length - 3] + "..." if len(text) > max_length else text

    for idx, assignment in enumerate(assignments, start=1):
        try:
            assignment_name = assignment.get("name", "Unnamed Assignment")
            if status_callback:
                status_callback(f"Processing {idx}/{len(assignments)}: {assignment_name}")
            raw_description = assignment.get("description", "") or ""
            plain_description = re.sub('<[^<]+?>', '', raw_description).strip()
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
            properties = {"Name": {"title": [{"text": {"content": assignment_name}}]}}
            if due_date_iso:
                properties["Due Date"] = {"date": {"start": due_date_iso}}
            if course_name:
                properties["Course"] = {"rich_text": [{"text": {"content": course_name}}]}
            if url:
                properties["URL"] = {"url": url}
            existing_page_id = existing_pages_map.get(assignment_name)
            if existing_page_id:
                should_update = False
                if due_date_iso:
                    assignment_date = datetime.date.fromisoformat(due_date_iso)
                    today = datetime.date.today()
                    two_weeks_from_now = today + datetime.timedelta(weeks=2)
                    if today <= assignment_date <= two_weeks_from_now:
                        should_update = True
                if should_update:
                    if status_callback: status_callback(f"Updating upcoming assignment: {assignment_name}")
                    update_url = f"https://api.notion.com/v1/pages/{existing_page_id}"
                    update_payload = {"properties": properties}
                    update_resp = requests.patch(update_url, headers=headers, json=update_payload)
                    if update_resp.ok:
                        if status_callback: status_callback(f"🔄 Updated '{assignment_name}' in Notion.")
                    else:
                        if status_callback: status_callback(f"⚠️ Failed to update '{assignment_name}': {update_resp.text}")
                else:
                    if status_callback: status_callback(f"Skipping duplicate (not due soon): {assignment_name}")
                continue
            description_content = truncate_text(plain_description)
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

