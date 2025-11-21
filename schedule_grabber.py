#!/usr/bin/env python3
"""
schedule_grabber.py
-------------------
CLI utility to fetch assignments from Canvas using the existing module
helpers and write a normalized JSON file to the app-safe schedules folder.

Usage examples:
  python3 schedule_grabber.py --out schedules/latest.json
  python3 schedule_grabber.py --dry-run

This tool reads credentials from the OS keyring (app name `NotionSync`) and
from a `credentials.json` in the app data path. It uses the same Canvas
helpers in `canvas_notion_calendar_db_v1.py` to fetch assignments.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
import keyring

from canvas_notion_calendar_db_v1 import get_canvas_assignments

APP_NAME = "NotionSync"

def get_safe_paths():
    if sys.platform == "darwin":
        app_support_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', APP_NAME)
    elif sys.platform == "win32":
        app_support_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_NAME)
    else:
        app_support_dir = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)
    os.makedirs(app_support_dir, exist_ok=True)
    schedules_dir = os.path.join(app_support_dir, 'schedules')
    os.makedirs(schedules_dir, exist_ok=True)
    return {"root": app_support_dir, "schedules": schedules_dir, "credentials": os.path.join(app_support_dir, 'credentials.json')}


def normalize_assignment(a):
    # Return a stable, small dict for downstream processing
    due = a.get('due_at') or a.get('lock_at') or a.get('created_at')
    due_date = None
    if due:
        try:
            # leave ISO as-is; callers can parse
            due_date = due.split('T')[0]
        except Exception:
            due_date = None

    return {
        "id": a.get('id'),
        "name": a.get('name'),
        "due_at": due,
        "due_date": due_date,
        "course_name": a.get('course_name'),
        "description": a.get('description'),
        "html_url": a.get('html_url')
    }


def load_local_creds(paths):
    data = {}
    if os.path.exists(paths['credentials']):
        try:
            with open(paths['credentials'], 'r') as f:
                data = json.load(f)
        except Exception:
            pass
    return data


def main():
    p = argparse.ArgumentParser(description="Fetch Canvas assignments and write normalized JSON.")
    p.add_argument('--out', '-o', help='Output file path (defaults to app schedules folder with timestamp)')
    p.add_argument('--dry-run', action='store_true', help='Fetch and print summary but do not write file')
    args = p.parse_args()

    paths = get_safe_paths()
    creds = load_local_creds(paths)

    canvas_key = keyring.get_password(APP_NAME, 'canvas_key') or creds.get('canvas_key')
    base_url = creds.get('canvas_url') or 'https://keyinstitute.instructure.com/api/v1'
    use_default = creds.get('use_default_url', True)
    if use_default:
        base_url = 'https://keyinstitute.instructure.com/api/v1'

    buckets = creds.get('buckets', None)
    selected_course_ids = creds.get('selected_course_ids', None)

    if not canvas_key:
        print('Canvas API key not found in keyring or credentials.json')
        sys.exit(1)

    assignments = get_canvas_assignments(canvas_key, base_url, buckets, selected_course_ids, status_callback=print)

    normalized = [normalize_assignment(a) for a in assignments]

    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    default_out = os.path.join(paths['schedules'], f'assignments-{ts}.json')
    out_path = args.out or default_out

    if args.dry_run:
        print(f'Fetched {len(normalized)} assignments. Sample:')
        for a in normalized[:5]:
            print(json.dumps(a, indent=2))
        return

    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(), "assignments": normalized}, f, indent=2)
        print(f'Wrote {len(normalized)} assignments to {out_path}')
    except Exception as e:
        print('Failed to write output:', e)
        sys.exit(2)


if __name__ == '__main__':
    main()
