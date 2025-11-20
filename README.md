# NotionSync

> Status: Early development. Functionality is limited and subject to rapid change. This README focuses on honesty and clarity until more features are implemented.

## Why
NotionSync is an experiment to build a Python-based tool for reliably pulling (and eventually optionally pushing) structured data from a Notion workspace into local, versionable files. The long‑term intent is reproducible exports for backups, analysis, and developer workflows.

## Project Maturity
- API design: exploratory
- Stability: very low
- Documentation: skeletal
- Backwards compatibility: NOT guaranteed

If you find claims in this README that do not match the code, please open an issue—accuracy matters more than marketing right now.

## Current Capabilities (Implemented So Far)
The following list should reflect ONLY what actually works today. Please edit to match reality:
- Basic project scaffolding in Python
- Environment variable loading (e.g., for a Notion API token)
- (Add/remove items here as features become real)

Anything not listed here should be assumed NOT implemented yet.

## Planned (Not Yet Implemented)
These are goals—not promises. They will move around as the project evolves:
- Pull (download) sync of pages and databases into Markdown / JSON
- Export formatting (Markdown, HTML, JSON)
- Optional push of edited local Markdown back to Notion
- Incremental / delta sync & change detection
- Plugin system for custom exporters / processors
- CI workflow for scheduled sync (GitHub Actions)

## Getting Started (Minimal)
```bash
# Clone
git clone https://github.com/fcanas574/NotionSync.git
cd NotionSync

# (Optional) create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies (if/when requirements.txt or pyproject.toml exists)
pip install -r requirements.txt
```

Create a `.env` (if env loading exists):
```
NOTION_API_TOKEN=secret_xxx
```

If the sync CLI or script does not yet exist, this section will be updated once a usable entrypoint is added.

## Usage
(Placeholder) When a CLI command is available, examples will go here. Until then, there is no supported user flow.

## Development
```bash
# Run tests (add once tests exist)
pytest -v
```

Code style and tooling will be documented after they are actually configured (e.g., black, ruff, mypy). Avoid adding badges or claims until tooling is in place.

## Contributing
Right now the best contributions are:
1. Opening issues that precisely describe bugs or gaps.
2. Proposing minimal, well-tested incremental improvements.
3. Suggesting ways to keep feature claims honest.

Feel free to open a PR—but expect churn. Please keep changes small and focused.

## Troubleshooting (Will Expand Later)
| Symptom | Cause | Action |
|---------|-------|--------|
| Import errors | Missing dependencies | Verify and install requirements once defined |
| No output | Feature not implemented | Check README; open issue if unclear |

## Roadmap Philosophy
The roadmap here is intentionally lightweight. Items may be dropped if they add complexity without clear user value. Honest pruning is a success, not a failure.

## FAQ
**Is sync working?** Likely only basic scaffolding unless otherwise stated above.
**Can I rely on this for backups yet?** No—wait for explicit confirmation in the Current Capabilities section.
**Will you implement push sync?** Possibly, but only after pull is robust.

## License
License not finalized yet. (Add LICENSE file before declaring.)

## Acknowledgments
Thanks to the Notion API and Python open source ecosystem. More detailed credits will be added once external libraries and patterns solidify.

---
> Reminder: Keep this README aligned with reality. Update "Current Capabilities" before announcing new features anywhere else.