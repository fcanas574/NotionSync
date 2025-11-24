# NotionSync — Web Edition

A cross-platform web application to sync Canvas assignments to a Notion database, with a simple scheduler and a time-block generator. Accessible from any device with a web browser - desktop, mobile, tablet, or anywhere!

## What's in this version
- **Web-based interface**: Access from any device with a web browser - no installation needed on client devices!
- **Cross-platform**: Works on Windows, macOS, Linux, mobile devices, and tablets
- **Modern UI**: Clean, responsive design that adapts to all screen sizes
- **Secure credential storage**: Canvas/Notion API keys saved to the OS keychain via `keyring`
- **All original features**:
  - Daily background sync using `schedule`
  - Settings for bucket selection (Past/Undated/Upcoming/Future/Ungraded)
  - Course selection: Fetch Canvas courses and persist selected IDs for targeted syncs
  - Time Block Generator: Plan study blocks from Canvas assignments with optional Notion export
  - Live sync status: Real-time updates as sync progresses

## Why Web-Based?

The original PyQt6 desktop application has been replaced with a Flask web application to provide:
- **True cross-platform compatibility**: Access from any device (desktop, mobile, tablet)
- **No installation required**: Users just need a web browser
- **Easier deployment**: Can be hosted on a server for remote access
- **Simpler maintenance**: Web technologies are easier to update and debug

## Requirements
- Python 3.10+
- Dependencies in `requirements.txt` (notably: Flask, schedule, keyring, requests)

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Running

### Web Interface (Recommended)

Start the web server:

```bash
python3 app.py
```

Then open your browser to: **http://localhost:5000**

The web interface will be accessible from any device on your local network.

### Background Sync (Command Line)

One-off background sync (no GUI):

```bash
python3 app.py --background
```

## First-time setup
1. Access the web interface at http://localhost:5000
2. Navigate to the "Credentials" page
3. Enter Canvas API Key, Notion API Key, and Notion Database ID
4. Optionally configure Canvas Base URL or use the default institution
5. Go to "Settings" to select sync buckets
6. (Optional) Go to "Courses" to select which courses to sync

Notes:
- API keys are saved to the OS keychain; the JSON config omits secrets
- On first successful sync, the app marks "first_sync_complete" to adjust future behavior

## Notion database compatibility
The app checks and ensures required database properties. It logs progress and will warn if the schema is incompatible.

## Time Block Generator
1. Navigate to "Time Blocks" page
2. Configure block length and daily max
3. Optionally provide an availability JSON
4. Choose to preview or export directly to Notion

## Features

### Dashboard
- One-click sync with real-time progress updates
- Quick access to all features
- Status overview

### Credentials Management
- Secure storage using OS keychain
- Easy credential updates
- Built-in help for finding credentials

### Course Selection
- View all your Canvas courses
- Select which courses to sync
- Saves preferences for future syncs

### Settings
- Configure sync buckets (Past, Undated, Upcoming, Future, Ungraded)
- Set up automatic daily sync scheduling
- Customize sync behavior

### Time Block Generator
- Generate study time blocks from assignments
- Configure block duration and daily limits
- Export to Notion or preview

### Logs
- View detailed sync logs
- Track sync history
- Troubleshoot issues

## Deployment Options

### Local Use
Run on your computer and access from any device on your local network.

### Server Deployment
Deploy to a server (e.g., DigitalOcean, AWS, Heroku) for access from anywhere.

### Docker (Future)
A Docker container can be created for even easier deployment.

## Data locations
- Config/Logs: OS app data folder (e.g., macOS: `~/Library/Application Support/NotionSync/`)
- Secrets: OS keychain via `keyring` (no API keys in JSON by design)

## Migration from PyQt6

If you were using the old PyQt6 version:
- Your credentials and configuration files are compatible
- The web version uses the same data storage locations
- All features have been migrated to the web interface
- Simply install the new requirements and run `app.py`

## Known limitations
- Scheduler/daemon mode needs to be implemented for web version
- Mobile UI is functional but can be further optimized

## Contributing
Contributions are welcome! This web-based approach makes it easier for developers to contribute without needing Qt expertise.

## License
See LICENSE file for details.
