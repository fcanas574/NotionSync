# NotionSync

> A Python-powered utility for synchronizing data from your Notion workspace (pages, databases, and blocks) to local artifacts (files, structured exports) and optionally pushing changes back.

---
## Table of Contents
1. Overview
2. Features
3. Architecture
4. Getting Started
5. Configuration
6. Usage
7. Automation & CI
8. Development
9. Roadmap
10. Contributing
11. Troubleshooting
12. FAQ
13. Security
14. Changelog
15. License

---
## 1. Overview
NotionSync aims to provide a reproducible, scriptable way to mirror Notion content locally for backup, analysis, version control, or transformation. While the Notion UI is great for collaboration, developers often need structured exports or a pipeline-friendly interface.

This project is written primarily in Python (≈93%) with some supporting HTML (≈7%) for rendered previews or UI components.

> NOTE: Because very little project-specific info was provided, some sections include TODO items. Replace these with accurate descriptions as the implementation evolves.

---
## 2. Features
- Incremental sync of Notion pages & databases via the official Notion API.
- Local export formats (Markdown, JSON, HTML) (TODO: confirm implemented formats).
- Pluggable transformation layer (e.g., convert databases to CSV / Pandas DataFrames).
- Optional reverse sync (push edited local Markdown back to Notion) (TODO: implement / confirm).
- Environment-based configuration (.env support).
- Dry-run mode for safe testing.
- Logging with configurable verbosity.
- Extensible target outputs (filesystem today; future S3 / Git repo integration?).

---
## 3. Architecture
High-level components (expected / recommended):
```
notionsync/
  api/          # Thin wrappers around Notion REST API calls
  models/       # Data classes representing Notion entities (Page, Database, Block)
  exporters/    # Format-specific exporters (markdown.py, html.py, json.py)
  sync/         # Orchestration logic for pull/push operations
  cli.py        # CLI entrypoint (argparse / click)
  config.py     # Config loading (env vars, overrides)
  utils/        # Common helpers (logging, time, caching)
  __init__.py
```
> Adjust this layout to match your actual repository. If files differ, update this section.

Data Flow:
1. Load configuration (env vars, arguments).
2. Fetch Notion objects via API client.
3. Normalize into internal model layer.
4. Export/render into chosen formats.
5. (Optional) Detect local edits & apply updates back to Notion.

---
## 4. Getting Started
### Prerequisites
- Python 3.10+ (recommend 3.11 or newer)
- A Notion integration with a valid API token ([Create one here](https://www.notion.so/my-integrations)).
- Access to the Notion pages/databases you intend to sync (shared with the integration).

### Installation
```bash
# Clone the repository
git clone https://github.com/fcanas574/NotionSync.git
cd NotionSync

# (Optional) create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (assuming a requirements.txt or pyproject.toml exists)
pip install -r requirements.txt  # or: pip install .
```

### Quick Setup
Create a `.env` file in the project root:
```
NOTION_API_TOKEN=secret_xxx
NOTION_DATABASE_IDS=xxxx-uuid-1,yyyy-uuid-2  # Optional: comma-separated list
OUTPUT_DIR=./export
SYNC_MODE=pull    # pull | push | bidirectional (TODO: confirm implemented values)
LOG_LEVEL=INFO
```

---
## 5. Configuration
Environment Variables (proposed):
| Name | Required | Description |
|------|----------|-------------|
| NOTION_API_TOKEN | Yes | API token from your Notion integration. |
| NOTION_DATABASE_IDS | No | Comma-separated database IDs to target. If omitted, may sync all accessible pages (TODO). |
| OUTPUT_DIR | No | Directory to write exported artifacts. Default: `./export`. |
| SYNC_MODE | No | Operation direction (pull / push / bidirectional). |
| LOG_LEVEL | No | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| EXPORT_FORMATS | No | Comma-separated list (e.g., `markdown,html,json`). |
| RATE_LIMIT_SLEEP | No | Seconds to wait when rate limit encountered. |

Command-line flags (example / hypothetical):
```bash
python -m notionsync.cli \
  --mode pull \
  --formats markdown json \
  --output ./export \
  --database xxxx-uuid
```
> Run `python -m notionsync.cli --help` once implemented to view authoritative options.

---
## 6. Usage
### Pull (Download) Content
```bash
python -m notionsync.cli --mode pull --formats markdown,json --output ./export
```

### Push (Upload Local Changes) (TODO: confirm availability)
```bash
python -m notionsync.cli --mode push --source ./export/markdown
```

### Bidirectional Sync (Experimental) (TODO)
```bash
python -m notionsync.cli --mode bidirectional --formats markdown
```

### Scheduling with Cron
```cron
# Sync every hour
0 * * * * /usr/bin/env bash -c 'cd /path/to/NotionSync && source .venv/bin/activate && python -m notionsync.cli --mode pull >> sync.log 2>&1'
```

### GitHub Actions (Example Workflow Snippet)
```yaml
name: Notion Sync
on:
  schedule:
    - cron: '0 * * * *'
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
          NOTION_API_TOKEN: ${{ secrets.NOTION_API_TOKEN }}
        run: |
          python -m notionsync.cli --mode pull --formats markdown,json --output export
      - name: Commit Artifacts
        run: |
          git config user.name 'github-actions'
          git config user.email 'github-actions@users.noreply.github.com'
          git add export
          git commit -m 'Automated Notion sync' || echo 'No changes'
          git push
```

---
## 7. Automation & CI
Recommended checks:
- Lint (ruff / flake8 / pylint).
- Formatting (black).
- Type checking (mypy, pyright).
- Unit tests (pytest) with coverage.
- Security scanning (bandit, pip-audit).

---
## 8. Development
### Project Setup
```bash
pip install -r requirements-dev.txt  # if exists
pre-commit install                   # if using pre-commit
```

### Running Tests
```bash
pytest -v
```

### Code Style
- Format: black
- Imports: isort (if configured)
- Lint: ruff (fast) or flake8

### Suggested Directory Conventions
Keep pure data models separate from API calls for testability.

### Commit Message Guidelines
Use Conventional Commits for clarity:
```
feat: add markdown exporter
fix: handle rate limit errors
chore: update dependencies
refactor: simplify sync loop
docs: improve README configuration section
```

---
## 9. Roadmap
| Milestone | Description | Status |
|-----------|-------------|--------|
| MVP Pull Sync | Export pages & databases to Markdown/JSON | In Progress |
| HTML Export | Render pages to standalone HTML | TODO |
| Push Sync | Update Notion from local edits | TODO |
| Incremental Changes | Delta sync & change detection | TODO |
| Plugin System | Custom exporters & processors | TODO |
| Scheduling Utilities | Built-in CLI schedule helpers | TODO |

---
## 10. Contributing
1. Fork the repo & create a feature branch.
2. Make changes with adequate tests.
3. Run linting & formatting tools.
4. Open a Pull Request describing changes & rationale.
5. Ensure CI passes before requesting review.

### Reporting Issues
Open an issue with:
- Expected behavior
- Actual behavior
- Steps to reproduce
- Logs / screenshots (if helpful)

---
## 11. Troubleshooting
| Symptom | Possible Cause | Resolution |
|---------|----------------|-----------|
| 401 Unauthorized | Invalid or missing API token | Regenerate integration token & update .env |
| Missing Pages | Integration not shared with page | Share the page/database with the integration in Notion UI |
| Rate Limit Errors | Too many requests quickly | Implement exponential backoff / increase RATE_LIMIT_SLEEP |
| Empty Exports | Wrong database IDs or filters | Verify IDs; test with a single known page |

Enable debug logging:
```bash
LOG_LEVEL=DEBUG python -m notionsync.cli --mode pull
```

---
## 12. FAQ
**Q: Does this replace Notion's built-in export?**  
A: It complements it by enabling incremental, scriptable syncs.

**Q: Are page relations preserved?**  
A: Planned via internal graph modeling (TODO).

**Q: Is real-time sync supported?**  
A: Not currently; consider periodic cron or GitHub Actions.

---
## 13. Security
- Store API tokens in environment variables or secrets providers (never commit them).
- Use least-privilege: only share necessary pages/databases with the integration.
- Review dependency updates regularly.

---
## 14. Changelog
Maintain a `CHANGELOG.md` following [Keep a Changelog](https://keepachangelog.com/) principles (TODO: initialize).

---
## 15. License
Specify a license (e.g., MIT, Apache 2.0). (TODO: Add LICENSE file and reference here.)

---
## Acknowledgments
- Notion API Team & docs.
- Open-source Python ecosystem.

---
## Next Steps for This README
- Replace TODO sections with actual implementation notes.
- Add real examples (before/after sync).
- Include performance benchmarks if relevant.

---
> Feel free to modify any placeholder sections as the project matures.