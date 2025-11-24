# NotionSync — Web Edition

A web-based application to sync Canvas assignments to a Notion database. This is a Django-based migration from the original PyQt6 desktop application.

## Features

- **User Authentication**: Secure login and registration system
- **API Credential Management**: Store Canvas and Notion API keys securely in the database
- **Manual Sync**: Trigger Canvas to Notion synchronization from the web dashboard
- **Sync History**: Track all sync operations with detailed logs
- **Course Selection**: Choose which Canvas courses to sync
- **Customizable Buckets**: Select which assignment categories to sync (past, undated, upcoming, future, ungraded)

## Requirements

- Python 3.10+
- Dependencies in `requirements.txt` (Django, requests, schedule, python-dateutil, colorama)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/fcanas574/NotionSync.git
cd NotionSync
```

2. Install dependencies:
```bash
python3 -m pip install -r requirements.txt
```

3. Run migrations:
```bash
python3 manage.py migrate
```

4. Create a superuser (optional, for admin access):
```bash
python3 manage.py createsuperuser
```

## Running the Application

Start the development server:
```bash
python3 manage.py runserver
```

Then open your browser to `http://localhost:8000`

## First-time Setup

1. Register a new account or login
2. Go to Settings and enter your API credentials:
   - **Canvas API Key**: Get from Canvas Account → Settings → Approved Integrations
   - **Canvas Base URL**: Use default or enter custom URL
   - **Notion API Key**: Create integration at [notion.so/my-integrations](https://www.notion.so/my-integrations)
   - **Notion Database ID**: 32-character hex ID from your database URL
3. Select which assignment buckets to sync
4. Save settings

## Using the Application

### Dashboard
- View sync status
- Run manual synchronization
- See recent sync history

### Settings
- Configure API keys and credentials
- Choose Canvas base URL
- Select assignment buckets to sync
- Get help on obtaining API keys

### Sync History
- View detailed logs of all sync operations
- Check sync status and assignment counts
- Debug any sync issues

## Data Storage

- **User Data**: SQLite database (`db.sqlite3`)
- **API Credentials**: Stored encrypted in the database (replaces keyring from desktop app)
- **Sync Logs**: Historical record of all sync operations

## Security Notes

- API keys are stored in the database
- For production use, ensure:
  - `DEBUG = False` in settings
  - Set a strong `SECRET_KEY`
  - Use HTTPS
  - Configure proper database (PostgreSQL, MySQL, etc.)
  - Use environment variables for sensitive settings

## Migration from Desktop App

This web version replaces the PyQt6 desktop application. Key differences:

- **No local keyring**: Credentials stored in database
- **Web interface**: Access from any browser
- **Multi-user**: Support for multiple users with separate credentials
- **Sync logs**: Built-in history tracking

## Core Business Logic

The core sync logic from the desktop app has been extracted to:
- `canvas_notion_calendar_db_v1.py`: Canvas and Notion API interactions
- `sync/services.py`: Service layer for sync operations
- `time_blocker.py`: Time blocking functionality (unchanged)
- `schedule_grabber.py`: CLI utility for assignment fetching (unchanged)

## Admin Interface

Access the Django admin at `/admin/` to:
- Manage users and profiles
- View sync logs
- Configure user settings

## Production Deployment

For production deployment:
1. Set environment variables for sensitive data
2. Use a production-grade database (PostgreSQL recommended)
3. Configure static files with `python3 manage.py collectstatic`
4. Use a WSGI server (Gunicorn, uWSGI)
5. Set up HTTPS with nginx or Apache
6. Enable Django security features

## Legacy Desktop App

The original PyQt6 desktop application code remains in `CanvasAssignments.py` for reference but is no longer the primary interface.

## License

Same as the original NotionSync project.
