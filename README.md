# NotionSync — beta-0.1

A desktop helper app to sync Canvas assignments to a Notion database, with a simple scheduler and a time-block generator. This branch (beta-0.1) includes a refreshed UI/UX, safer credential storage, and several stability fixes.

## What’s in this branch
- Sidebar UX polish: smooth collapse/expand animation, text fade, width memory, consistent icon/text styling (font-size 11px, light text color).
- Safer paths: credentials/logs stored under OS-specific app support (macOS: `~/Library/Application Support/NotionSync/`).
- Key storage: Canvas/Notion API keys saved to the OS keychain via `keyring`.
- Tray integration: menu for running sync, showing window, quitting.
- Scheduler: daily background sync using `schedule` (optional daemon mode).
- Settings dialog: 
  - Buckets (Past/Undated/Upcoming/Future/Ungraded) selection.
  - Startup preference (OS login item on macOS/Windows).
  - Advanced toggle retained for future features.
- Course selection: fetch Canvas courses and persist selected IDs for targeted syncs.
- Time Block Generator: plan study blocks from Canvas assignments; optional Notion export.
- Diagnostics tooling: `scripts/capture_sidebar_gif.py` to capture a GIF + JSON metrics of sidebar behavior for regressions.

## Requirements
- Python 3.10+
- Dependencies in `requirements.txt` (notably: PyQt6, schedule, keyring, requests, Pillow for capture script, optional `qt-material`).

Install dependencies:

```
python3 -m pip install -r requirements.txt
```

## Running
Interactive app (GUI):

```
python3 CanvasAssignments.py
```

Background scheduler daemon (tray + daily sync at configured time):

```
python3 CanvasAssignments.py --daemon
```

One-off background sync (no full GUI):

```
python3 CanvasAssignments.py --background
```

## First-time setup
1. Enter Canvas API Key, Notion API Key, and Notion Database ID.
2. Optionally choose Canvas Base URL or use the default institution.
3. Use Settings to select sync buckets and enable startup.
4. (Optional) Load courses and select which to sync.

Notes:
- API keys are saved to the OS keychain; the JSON config omits secrets.
- On first successful sync, the app marks "first_sync_complete" to adjust future behavior.

## Notion database compatibility
The app checks and ensures required database properties. It logs progress and will warn if the schema is incompatible.

## Time Block Generator
- Configure block length and daily max.
- Optionally provide an availability JSON.
- Dry-run preview or export directly to Notion.

## Packaging
A `NotionSync.spec` (PyInstaller) file is included. Typical build:

```
pyinstaller NotionSync.spec
```

Artifacts will appear under `build/NotionSync/` and `dist/` (if enabled in the spec).

## Diagnostics & QA (optional)
Sidebar capture and metrics:

```
python3 scripts/capture_sidebar_gif.py
```

Outputs:
- `sidebar_capture.gif` — visual of the expand/collapse cycle
- `sidebar_metrics.json` — per-frame geometry + state for analysis

## Known limitations (beta)
- UI theming uses `qt-material` when available; otherwise falls back to bundled QSS.
- Linux autostart integration not fully implemented.
- Notion database schema must contain/allow the required date property.

## Data locations
- Config/Logs: OS app data folder (e.g., macOS: `~/Library/Application Support/NotionSync/`)
- Secrets: OS keychain via `keyring` (no API keys in JSON by design)
