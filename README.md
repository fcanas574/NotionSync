# NotionSync

> Status: Early development. Focus: Sync assignments from Canvas (Instructure) courses into one or more Notion databases. This README aims to stay strictly truthful about capabilities.

## Overview
NotionSync currently targets ONE problem: pulling assignment data from Canvas LMS and reflecting it inside a Notion database so you can manage deadlines in a place you already organize work.

Canvas → Notion flow (pull only):
1. Call Canvas API for a set of course IDs.
2. Fetch assignments (optionally filtering by date / published status).
3. Upsert pages/rows in a Notion database using stable assignment identifiers.
4. Update changed fields (due date, name, html description stripped to markdown/plain text, points, etc.).

No data is pushed back to Canvas. Notion edits do NOT change Canvas.

## Current Capabilities (Implemented)
Please adjust this list if something is NOT actually working yet.
- Fetch assignments from specified Canvas courses using an API token.
- Create a Notion page/row per assignment if it does not already exist.
- Update existing Notion entries when assignment metadata changes (e.g., due_at).
- Store Canvas assignment ID for stable deduplication (prevents duplicates).
- Basic mapping of properties (e.g., Name, Due Date, Course, Points, URL).
- Environment-based configuration via `.env` (if implemented in code).
- Simple logging (INFO/DEBUG levels) (adjust if not present).

## Not Yet Implemented (Planned / Aspirational)
These items are NOT done unless you explicitly add them to Current Capabilities.
- Sync of assignment state changes (e.g., marking complete automatically).
- Sync of submissions / grades / score.
- Sync of modules, announcements, discussions, or syllabus.
- Deletion or archival of assignments removed from Canvas.
- Attachments / embedded media fetch & storage.
- Rate-limit adaptive backoff & caching layer.
- Push from Notion back to Canvas (no intent short-term).
- Real-time updates (webhooks) — Canvas webhooks are limited; likely polling only.

## Data Mapping (Default Suggestion)
Canvas Field → Notion Property
- assignment.id → Number or text property ("Canvas ID")
- name → Title
- due_at → Date property (Due)
- unlock_at / lock_at → Separate date properties (Unlock / Lock) (optional)
- points_possible → Number (Points)
- html_url → URL property (Canvas Link)
- course_id → Select / Relation / Text (Course)
- submission_types → Multi-select (Submission Types)
- description (HTML) → Rich text (stripped or lightly converted)

> Adjust to match whatever properties you have actually defined in your Notion database.

## Configuration
Environment variables (proposed — include only those you really use):
| Variable | Required | Description |
|----------|----------|-------------|
| CANVAS_API_TOKEN | Yes | Canvas API token (generate in Canvas account settings). |
| CANVAS_BASE_URL | Yes | Base Canvas domain, e.g. `https://yourinstitution.instructure.com`. |
| CANVAS_COURSE_IDS | Yes | Comma-separated list of numeric course IDs to sync. |
| NOTION_API_TOKEN | Yes | Notion integration secret. Share the target database with this integration. |
| NOTION_ASSIGNMENTS_DATABASE_ID | Yes | The Notion database ID receiving assignments. |
| TIMEZONE | No | IANA timezone for localizing dates (default UTC). |
| DRY_RUN | No | If `true`, performs fetch & logs without writing to Notion. |
| LOG_LEVEL | No | `DEBUG`, `INFO`, etc. |
| DATE_RANGE_DAYS | No | Limit assignments to next N days (if filtering implemented). |

Example `.env`:
```
CANVAS_API_TOKEN=secret_canvas_xxx
CANVAS_BASE_URL=https://mycollege.instructure.com
CANVAS_COURSE_IDS=12345,67890
NOTION_API_TOKEN=secret_notion_xxx
NOTION_ASSIGNMENTS_DATABASE_ID=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
LOG_LEVEL=INFO
DRY_RUN=false
```

## Installation
```bash
git clone https://github.com/fcanas574/NotionSync.git
cd NotionSync
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt  # if exists
```

## Running (Example Placeholder)
Replace with the actual entrypoint you implemented (script name / CLI module).
```bash
python -m notionsync.canvas_to_notion --config .env
```
Or if a script:
```bash
python sync_canvas_assignments.py
```
Add flags once they exist:
```bash
python sync_canvas_assignments.py --courses 12345 67890 --dry-run
```

## Scheduling (Cron Example)
```cron
# Pull assignments every morning at 06:10
10 6 * * * /usr/bin/env bash -c 'cd /path/to/NotionSync && source .venv/bin/activate && python sync_canvas_assignments.py >> canvas-sync.log 2>&1'
```

## GitHub Actions (Placeholder Workflow)
Only add after the script is stable.
```yaml
name: Canvas Assignment Sync
on:
  schedule:
    - cron: '15 * * * *'
  workflow_dispatch:
jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install
        run: |
          pip install -r requirements.txt
      - name: Run Sync
        env:
          CANVAS_API_TOKEN: ${{ secrets.CANVAS_API_TOKEN }}
          NOTION_API_TOKEN: ${{ secrets.NOTION_API_TOKEN }}
          CANVAS_BASE_URL: ${{ vars.CANVAS_BASE_URL }}
          CANVAS_COURSE_IDS: ${{ vars.CANVAS_COURSE_IDS }}
          NOTION_ASSIGNMENTS_DATABASE_ID: ${{ vars.NOTION_ASSIGNMENTS_DATABASE_ID }}
        run: |
          python sync_canvas_assignments.py
```

## Error Handling & Limitations
| Symptom | Likely Cause | Suggested Action |
|---------|--------------|------------------|
| 401 from Canvas | Invalid/expired token | Regenerate API token. |
| 404 course | Wrong course ID or insufficient permissions | Verify numeric ID; confirm token access. |
| Notion write fails | Integration not shared with database | Share database with integration in Notion. |
| Duplicate pages | Missing unique Canvas ID property check | Ensure assignment ID used as key. |
| HTML noise in description | No sanitization yet | Strip tags or implement markdown conversion. |

## Development
```bash
# (Adjust paths based on actual repo structure)
pytest -v  # once tests exist
```
Tooling (only list after adopting): black, ruff, mypy, pre-commit.

## Contributing Guidelines (Early Stage)
- Keep PRs small & focused.
- Do not add features to README until they are merged & working.
- Include a brief summary of manual test steps in PR description.

## Roadmap (Truth-Oriented)
| Item | Goal | Status |
|------|------|--------|
| Core assignment pull | Basic field sync | Working (verify) |
| Robust field mapping | Add lock/unlock, submission types | Planned |
| Grade / score sync | Reflect grade & status | Planned |
| Attachment handling | Download or link files | Planned |
| Module sync | Mirror Canvas modules | Planned |
| Delta optimization | Reduce API calls via caching | Planned |
| Resync removals | Archive removed assignments | Planned |
| Webhook / near real-time | Faster updates (if feasible) | Investigating |

## FAQ
**Does it change Canvas data?** No. It only reads Canvas and writes to Notion.
**Can I edit Notion entries to reschedule assignments?** Yes locally, but those changes will NOT propagate back to Canvas.
**Why not push back to Canvas?** To avoid accidental grade or date changes; focus is safe read-only automation.
**Does it track submission state?** Not yet.
**How are duplicates avoided?** By storing Canvas assignment ID in a dedicated property and updating rather than creating if it exists.

## License
Add a LICENSE file before claiming a license here. (MIT is common if unsure.)

## Acknowledgments
- Canvas LMS API
- Notion API
- Python ecosystem

---
> Keep this README brutally accurate. Marketing later; truth now.
