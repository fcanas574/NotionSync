#!/usr/bin/env python3
"""
time_blocker.py
----------------
Creates study time blocks from assignments JSON and optionally exports them
to a Notion database (either existing or by creating a new DB under a parent page).

This is a pragmatic, greedy scheduler suitable as a starting point. It
supports a small availability schema (weekly recurring windows) and avoids
overlapping blocks when possible.

Availability JSON schema (example):
{
  "weekly": {
    "0": [{"start": "09:00", "end": "12:00"}, {"start": "18:00", "end": "21:00"}],
    "1": [...]
  },
  "exceptions": {
    "2025-11-25": [{"start": "10:00","end":"14:00"}]
  }
}

Usage examples:
  python3 time_blocker.py --assignments schedules/assignments-2025...json --availability availability.json --out schedules/blocks.json --export-notion --database-id <id>

"""
import argparse
import json
import os
import sys
from datetime import datetime, date, time, timedelta, timezone
from dateutil import parser as dateparser
import keyring
import textwrap
import re
try:
    from colorama import Fore, Style, init as _colorama_init
    COLORAMA_AVAILABLE = True
except Exception:
    COLORAMA_AVAILABLE = False

from canvas_notion_calendar_db_v1 import add_schedule_blocks_to_database

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


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def parse_time_str(tstr):
    return datetime.strptime(tstr, "%H:%M").time()


def build_weekly_windows(avail):
    # avail['weekly'] expected with weekday keys '0'..'6'
    weekly = {}
    for wd, windows in (avail.get('weekly') or {}).items():
        weekly[int(wd)] = [(parse_time_str(w['start']), parse_time_str(w['end'])) for w in windows]
    return weekly


def find_slot_for_block(windows_by_weekday, scheduled_on_day, target_date, block_minutes, daily_max_minutes=None):
    """
    Find a slot on or before target_date that can fit block_minutes, avoiding overlaps
    in scheduled_on_day (a dict date->list of (start_dt,end_dt)). Returns (start_iso,end_iso) or None.
    """
    days_back = 0
    max_lookback = 30
    while days_back <= max_lookback:
        d = target_date - timedelta(days=days_back)
        wd = d.weekday()
        windows = windows_by_weekday.get(wd, [])
        day_sched = scheduled_on_day.get(d.isoformat(), [])

        # For each window, try to fit the block from latest possible time backward
        for w_start, w_end in reversed(windows):
            w_start_dt = datetime.combine(d, w_start)
            w_end_dt = datetime.combine(d, w_end)
            # latest possible end is min(w_end, target_date end-of-day if same day)
            latest_end = min(w_end_dt, datetime.combine(d, time(23,59,59)))
            block_td = timedelta(minutes=block_minutes)
            candidate_end = latest_end
            candidate_start = candidate_end - block_td
            # Move candidate earlier until it doesn't overlap existing scheduled blocks
            conflict = True
            attempts = 0
            while candidate_start >= w_start_dt and attempts < 48:
                overlap = False
                for s,e in day_sched:
                    if not (candidate_end <= s or candidate_start >= e):
                        overlap = True; break
                if not overlap:
                    # optionally respect daily max minutes
                    if daily_max_minutes:
                        total_today = sum(int((e-s).total_seconds()/60) for s,e in day_sched)
                        if total_today + block_minutes > daily_max_minutes:
                            overlap = True
                    if not overlap:
                        return candidate_start.isoformat(), candidate_end.isoformat()
                # shift earlier by 15 minutes
                candidate_end = candidate_start
                candidate_start = candidate_end - block_td
                attempts += 1
        days_back += 1
    return None


def schedule_blocks(assignments, availability, block_minutes=90, daily_max_minutes=None,
                    include_short_quizzes=False, low_points_threshold=10, short_quiz_minutes=15,
                    points_scale=50, max_blocks_per_assignment=4):
    # Build weekly windows
    windows_by_weekday = build_weekly_windows(availability)
    scheduled = []
    scheduled_on_day = {}
    # Filter assignments: only include those with a due date within the next 14 days
    today = date.today()
    max_date = today + timedelta(days=14)

    filtered = []
    for a in assignments:
        # Prefer an explicit 'due_date' (YYYY-MM-DD), fall back to parsing 'due_at' ISO
        due_date_str = a.get('due_date')
        if not due_date_str:
            due_at = a.get('due_at') or a.get('lock_at') or a.get('created_at')
            if due_at:
                try:
                    due_dt_full = dateparser.isoparse(due_at)
                    due_date_str = due_dt_full.date().isoformat()
                except Exception:
                    due_date_str = None

        if not due_date_str:
            # Skip undated items for time-blocking
            continue

        try:
            due_dt = date.fromisoformat(due_date_str)
        except Exception:
            # If parsing fails, skip the assignment
            continue

        # Exclude overdue items
        if due_dt < today:
            continue

        # Only include assignments due within the next two weeks
        if due_dt > max_date:
            continue

        filtered.append((due_dt, a))

    # Sort filtered assignments by due date (earliest first)
    filtered.sort(key=lambda x: x[0])

    for due_dt, a in filtered:
        name = a.get('name')

        # Determine assignment type and scoring
        submission_types = a.get('submission_types') or []
        if isinstance(submission_types, str):
            # sometimes it's a comma-separated string
            submission_types = [s.strip() for s in submission_types.split(',') if s.strip()]

        is_quiz = bool(a.get('quiz_id')) or any(('quiz' in str(s).lower() or 'online_quiz' in str(s).lower()) for s in submission_types)
        is_on_paper = any(('on_paper' in str(s).lower() or 'in_class' in str(s).lower() or 'on_paper' == str(s).lower()) for s in submission_types)
        points = None
        try:
            points = float(a.get('points_possible')) if a.get('points_possible') is not None else None
        except Exception:
            points = None

        # If it's a timed low-point quiz, decide whether to skip or give a short block
        if is_quiz and points is not None and points <= low_points_threshold and not include_short_quizzes:
            # Skip scheduling for trivial timed quizzes
            continue

        # Start with 1 block by default
        n_blocks = 1
        est_minutes = a.get('estimated_minutes')
        if isinstance(est_minutes, (int, float)) and est_minutes > 0:
            from math import ceil
            n_blocks = max(1, min(max_blocks_per_assignment, ceil(est_minutes / block_minutes)))
        else:
            # ============================================
            # ENHANCED PRIORITY SCORING SYSTEM
            # ============================================
            score = 1.0
            
            # --- 1. POINTS-BASED SCORING (Grade Impact) ---
            # Higher point assignments likely have more grade impact
            if points is not None:
                if points >= 100:
                    score += 2.5  # Major assignment (100+ pts)
                elif points >= 50:
                    score += 1.5  # Significant assignment (50-99 pts)
                elif points >= 25:
                    score += 1.0  # Medium assignment (25-49 pts)
                elif points >= 10:
                    score += 0.5  # Small assignment (10-24 pts)
                # < 10 pts: no bonus (trivial)
            
            # --- 2. SUBMISSION TYPE SCORING ---
            # On-paper/in-class exams need more prep
            if is_on_paper:
                score += 2.0
            
            # File uploads and essays typically need more time
            submission_str = ' '.join(str(s).lower() for s in submission_types)
            if 'file_upload' in submission_str or 'online_upload' in submission_str:
                score += 0.5
            
            # --- 3. EXPLICIT PRIORITY FIELD ---
            pr = str(a.get('priority') or '').lower()
            if pr in ['high', 'urgent', 'exam', 'final', 'midterm', 'critical']:
                score += 1.5
            elif pr in ['medium', 'important']:
                score += 0.75
            
            # --- 4. KEYWORD DETECTION (English & Spanish) ---
            text_check = ' '.join(filter(None, [str(a.get('name') or ''), str(a.get('description') or '')])).lower()
            
            # High-priority keywords (major assessments) - +2.0
            high_priority_keywords = [
                # English
                'final exam', 'final project', 'midterm exam', 'midterm project',
                'capstone', 'thesis', 'dissertation', 'comprehensive',
                # Spanish
                'examen final', 'proyecto final', 'examen parcial', 'parcial',
                'tesis', 'trabajo final'
            ]
            
            # Medium-priority keywords (significant work) - +1.5
            medium_priority_keywords = [
                # English
                'exam', 'project', 'paper', 'essay', 'presentation', 'report',
                'portfolio', 'research', 'analysis', 'proposal',
                # Spanish
                'examen', 'proyecto', 'ensayo', 'presentación', 'presentacion',
                'informe', 'reporte', 'investigación', 'investigacion',
                'análisis', 'analisis', 'propuesta', 'trabajo'
            ]
            
            # Low-priority boost keywords (study aids) - +0.5
            low_priority_keywords = [
                # English
                'review', 'study guide', 'practice', 'prep', 'preparation',
                'draft', 'outline', 'summary', 'notes',
                # Spanish
                'repaso', 'guía de estudio', 'guia de estudio', 'práctica', 'practica',
                'preparación', 'preparacion', 'borrador', 'esquema', 'resumen', 'notas'
            ]
            
            # Check keywords in priority order (only apply highest match)
            keyword_bonus = 0
            for kw in high_priority_keywords:
                if kw in text_check:
                    keyword_bonus = 2.0
                    break
            
            if keyword_bonus == 0:
                for kw in medium_priority_keywords:
                    if kw in text_check:
                        keyword_bonus = 1.5
                        break
            
            if keyword_bonus == 0:
                for kw in low_priority_keywords:
                    if kw in text_check:
                        keyword_bonus = 0.5
                        break
            
            score += keyword_bonus
            
            # --- 5. URGENCY SCORING (Due Date Proximity) ---
            days_until_due = (due_dt - today).days
            if days_until_due <= 1:
                score += 1.5  # Due tomorrow or today - URGENT
            elif days_until_due <= 3:
                score += 1.0  # Due within 3 days - HIGH
            elif days_until_due <= 7:
                score += 0.5  # Due within a week - MEDIUM
            # > 7 days: no urgency bonus
            
            # --- 6. ASSIGNMENT NAME LENGTH HEURISTIC ---
            # Longer, more descriptive names often indicate complex assignments
            name_len = len(name) if name else 0
            if name_len > 50:
                score += 0.25  # Complex/detailed assignment name
            
            # ============================================
            # Map score to blocks (rounded), cap at max_blocks_per_assignment
            # ============================================
            n_blocks = int(min(max(1, round(score)), max_blocks_per_assignment))

        # Schedule the required number of blocks for this assignment. Each successful
        # block will reduce the available windows for subsequent calls.
        blocks_scheduled = 0
        for i in range(n_blocks):
            # For short, low-point quizzes, we may schedule a shorter block
            this_block_minutes = block_minutes
            if is_quiz and points is not None and points <= low_points_threshold and include_short_quizzes:
                this_block_minutes = short_quiz_minutes

            slot = find_slot_for_block(windows_by_weekday, scheduled_on_day, due_dt, this_block_minutes, daily_max_minutes)
            if not slot:
                # fallback: place at due date at 18:00 for this_block_minutes for remaining blocks
                start_dt = datetime.combine(due_dt, time(18,0)) - timedelta(minutes=this_block_minutes * (n_blocks - i - 1))
                end_dt = start_dt + timedelta(minutes=this_block_minutes)
                slot = (start_dt.isoformat(), end_dt.isoformat())

            if slot:
                s,e = slot
                scheduled.append({
                    'name': name,
                    'start': s,
                    'end': e,
                    'course': a.get('course_name'),
                    'url': a.get('html_url'),
                    'duration': this_block_minutes,
                    'description': a.get('description'),
                    'points': points,
                    'total_blocks': n_blocks,
                    'block_num': i + 1,
                    'due_date': due_dt.isoformat()
                })
                day_key = date.fromisoformat(s.split('T')[0]).isoformat()
                scheduled_on_day.setdefault(day_key, []).append((dateparser.isoparse(s), dateparser.isoparse(e)))
                blocks_scheduled += 1
            else:
                # unable to schedule; stop attempting further blocks for this assignment
                break

    return scheduled


def pretty_print_blocks(blocks, limit=10, width=80):
    """Nicely print scheduled blocks to the console for dry-run output.

    Shows a boxed, human-readable summary for each block including start/end,
    duration, course, link and a wrapped description.
    """
    for b in blocks[:limit]:
        try:
            s = dateparser.isoparse(b.get('start')).astimezone().strftime('%Y-%m-%d %H:%M')
            e = dateparser.isoparse(b.get('end')).astimezone().strftime('%Y-%m-%d %H:%M')
        except Exception:
            s = b.get('start') or ''
            e = b.get('end') or ''

        title = b.get('name') or '<no title>'
        course = b.get('course') or ''
        header = f"{title}  [{course}]" if course else title

        print('\u2500' * width)
        print(header)
        print(f"{s} → {e}   • {b.get('duration', '?')} min")
        if b.get('url'):
            print(f"Link: {b.get('url')}")

        desc = (b.get('description') or '').strip()
        if desc:
            print()
            print(textwrap.fill(desc, width=width))
    print('\u2500' * width)
    if len(blocks) > limit:
        print(f"... and {len(blocks)-limit} more blocks planned")


def text_print_blocks(blocks, limit=10, width=80):
    """Print really plain, human-readable text blocks with simple separators.

    This is intentionally minimal: title, course, start→end, duration, URL,
    and a wrapped description, separated by blank lines.
    """
    def _strip_html(text):
        if not text:
            return ''
        # Remove simple HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        # Collapse whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean

    def _rel_date_text(dt_str):
        try:
            dt = dateparser.isoparse(dt_str).astimezone()
            today = datetime.now(timezone.utc).astimezone().date()
            d = dt.date()
            days = (d - today).days
            if days < 0:
                return f"{d.isoformat()} (past)"
            if days == 0:
                return f"{d.isoformat()} (today)"
            if days == 1:
                return f"{d.isoformat()} (tomorrow)"
            return f"{d.isoformat()} (in {days} days)"
        except Exception:
            return dt_str or ''

    for b in blocks[:limit]:
        try:
            s_dt = dateparser.isoparse(b.get('start')).astimezone()
            e_dt = dateparser.isoparse(b.get('end')).astimezone()
            s = s_dt.strftime('%Y-%m-%d %H:%M')
            e = e_dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            s = b.get('start') or ''
            e = b.get('end') or ''

        title = (b.get('name') or '<no title>').strip()
        course = (b.get('course') or '').strip()
        header = f"{title} [{course}]" if course else title

        # Urgency marker if block is within next 2 days
        urgency = ''
        try:
            if s_dt:
                days_until = (s_dt.date() - datetime.now(timezone.utc).astimezone().date()).days
                if days_until <= 2:
                    urgency = ' (!)' 
        except Exception:
            pass

        print(f"{header}{urgency}")
        print(f"Start: {s}    End: {e}    • {b.get('duration', '?')} min")
        # relative date helpful hint
        rel = _rel_date_text(b.get('start'))
        if rel:
            print(f"When: {rel}")

        if course:
            print(f"Course: {course}")

        if b.get('url'):
            print(f"URL: {b.get('url')}")

        desc = _strip_html(b.get('description'))
        if desc:
            # truncate long descriptions but show a helpful preview
            max_chars = 400
            if len(desc) > max_chars:
                desc = desc[:max_chars].rsplit(' ', 1)[0] + '...'
            print()
            for line in textwrap.wrap(desc, width=width):
                print(line)

        print('---')
    if len(blocks) > limit:
        print(f"... and {len(blocks)-limit} more blocks planned")


def modern_print_blocks(blocks, limit=10, width=80):
    """Print a cleaner, colored output when `colorama` is available.

    Falls back to plain text if colorama isn't present.
    """
    use_color = COLORAMA_AVAILABLE

    def col(text, fg=None, bold=False):
        if not use_color:
            return text
        parts = []
        if fg:
            parts.append(getattr(Fore, fg.upper(), ''))
        if bold:
            parts.append(Style.BRIGHT)
        parts.append(text)
        parts.append(Style.RESET_ALL)
        return ''.join(parts)

    for b in blocks[:limit]:
        try:
            s_dt = dateparser.isoparse(b.get('start')).astimezone()
            e_dt = dateparser.isoparse(b.get('end')).astimezone()
            s = s_dt.strftime('%a %b %d %H:%M')
            e = e_dt.strftime('%a %b %d %H:%M')
        except Exception:
            s = b.get('start') or ''
            e = b.get('end') or ''

        title = (b.get('name') or '<no title>').strip()
        course = (b.get('course') or '').strip()

        header = f"{title} [{course}]" if course else title
        # urgency
        urgency = ''
        try:
            if s_dt:
                days_until = (s_dt.date() - datetime.now(timezone.utc).astimezone().date()).days
                if days_until <= 2:
                    urgency = col(' (!) ', fg='red', bold=True)
        except Exception:
            pass

        print(col(header, fg='cyan', bold=True) + (' ' + urgency if urgency else ''))
        print(col('When:', fg='green'), f"{s} → {e}", col('•', fg='yellow'), f"{b.get('duration', '?')} min")
        if course:
            print(col('Course:', fg='magenta'), course)
        if b.get('url'):
            print(col('Link:', fg='blue'), b.get('url'))

        desc = re.sub(r'<[^>]+>', '', (b.get('description') or '')).strip()
        if desc:
            max_chars = 500
            if len(desc) > max_chars:
                desc = desc[:max_chars].rsplit(' ', 1)[0] + '...'
            print()
            for line in textwrap.wrap(desc, width=width):
                print(line)

        print(col('-' * 40, fg='white'))

    if len(blocks) > limit:
        print(col(f"... and {len(blocks)-limit} more blocks planned", fg='yellow'))


def main():
    p = argparse.ArgumentParser(description='Create study time blocks from assignments JSON')
    p.add_argument('--assignments', '-a', required=True, help='Path to assignments JSON produced by schedule_grabber')
    p.add_argument('--availability', '-v', help='Availability JSON path (weekly schema described in help)')
    p.add_argument('--block-minutes', type=int, default=90)
    p.add_argument('--daily-max', type=int, help='Maximum study minutes per day')
    p.add_argument('--include-short-quizzes', action='store_true', help='Include short blocks for low-point timed quizzes')
    p.add_argument('--low-points-threshold', type=int, default=10, help='Max points to consider a quiz low-value (default: 10)')
    p.add_argument('--short-quiz-minutes', type=int, default=15, help='Minutes to allocate to short quizzes when included')
    p.add_argument('--max-blocks', type=int, default=4, help='Maximum number of blocks to allocate per assignment')
    p.add_argument('--out', '-o', help='Output schedule JSON path')
    p.add_argument('--export-notion', action='store_true', help='Export generated blocks to Notion')
    p.add_argument('--database-id', help='Target Notion database id')
    p.add_argument('--format', '-f', choices=['text', 'pretty', 'modern'], default='text', help='Output format for --dry-run')
    # NOTE: database creation removed. Provide an existing database id via --database-id to export.
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()

    paths = get_safe_paths()
    creds = {}
    if os.path.exists(paths['credentials']):
        try:
            with open(paths['credentials'], 'r') as f: creds = json.load(f)
        except Exception:
            pass

    assignments_data = load_json(args.assignments)
    assignments = assignments_data.get('assignments') if isinstance(assignments_data, dict) and 'assignments' in assignments_data else assignments_data

    availability = {'weekly': {}}
    if args.availability:
        availability = load_json(args.availability)
    else:
        # default availability: evenings 18:00-21:00 every weekday
        availability = {'weekly': {str(i): [{'start':'18:00','end':'21:00'}] for i in range(7)}}

    blocks = schedule_blocks(
        assignments,
        availability,
        block_minutes=args.block_minutes,
        daily_max_minutes=args.daily_max,
        include_short_quizzes=args.include_short_quizzes,
        low_points_threshold=args.low_points_threshold,
        short_quiz_minutes=args.short_quiz_minutes,
        max_blocks_per_assignment=args.max_blocks
    )

    ts = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    default_out = os.path.join(paths['schedules'], f'blocks-{ts}.json')
    out_path = args.out or default_out

    if args.dry_run:
        print(f'Planned {len(blocks)} blocks. Sample:')
        fmt = getattr(args, 'format', 'text')
        if fmt == 'pretty':
            pretty_print_blocks(blocks, limit=10, width=80)
        elif fmt == 'modern':
            # initialize colorama on Windows
            if COLORAMA_AVAILABLE:
                try:
                    _colorama_init()
                except Exception:
                    pass
            modern_print_blocks(blocks, limit=10, width=80)
        else:
            # default: simple plain text
            text_print_blocks(blocks, limit=10, width=80)
        return

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(), "blocks": blocks}, f, indent=2)
    print(f'Wrote {len(blocks)} blocks to {out_path}')

    if args.export_notion:
        notion_key = keyring.get_password(APP_NAME, 'notion_key') or creds.get('notion_key')
        if not notion_key:
            print('Notion API key not found in keyring or credentials.json')
            sys.exit(1)

        if not args.database_id:
            print('No database id provided. Use --database-id to export to an existing Notion database.')
            sys.exit(2)

        created = add_schedule_blocks_to_database(notion_key, args.database_id, blocks, status_callback=print)
        print(f'Exported {len(created)} blocks to Notion database {args.database_id}')


if __name__ == '__main__':
    main()
