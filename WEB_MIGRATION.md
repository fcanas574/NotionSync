# NotionSync Web Interface - Cross-Platform Solution

## Overview
This document explains the migration from PyQt6 to a web-based interface to make NotionSync accessible from all devices.

## Why Web-Based?

### The Problem with PyQt6
- **Desktop only**: Limited to Windows, macOS, and Linux desktop environments
- **Installation complexity**: Requires Qt libraries and PyQt6 bindings
- **No mobile support**: Cannot run on phones or tablets
- **Development complexity**: Qt has a steep learning curve

### The Web Solution
- **Universal access**: Works on any device with a web browser
- **No client installation**: Users just need to access a URL
- **Mobile-friendly**: Responsive design works on phones, tablets, and desktops
- **Easier development**: Standard HTML/CSS/JavaScript skills
- **Remote access**: Can be deployed to a server for access from anywhere

## Architecture

### Backend: Flask (Python)
- **app.py**: Main Flask application with all routes
- **Reuses existing modules**: `canvas_notion_calendar_db_v1.py`, `time_blocker.py`
- **Same data storage**: Uses OS-specific paths and keyring for credentials
- **Compatible**: Existing credentials and configuration files work without changes

### Frontend: HTML/CSS/JavaScript
- **Modern UI**: Clean, professional design with CSS Grid and Flexbox
- **Responsive**: Adapts to any screen size
- **Interactive**: Real-time sync status updates via AJAX
- **Accessible**: Works on any modern browser

## Features Migrated

### ✅ All Original Features Preserved
1. **Credentials Management** - Secure storage via OS keyring
2. **Canvas Course Selection** - Choose which courses to sync
3. **Sync Control** - One-click sync with real-time progress
4. **Settings** - Configure buckets and scheduling
5. **Time Block Generator** - Create and export study schedules
6. **Log Viewer** - View sync history and debug information

### 📱 New Benefits
- Access from mobile phones
- Access from tablets
- Access from any computer with a browser
- No installation required on client devices
- Can be accessed remotely if deployed to a server

## File Structure

```
NotionSync/
├── app.py                          # Flask web application (NEW)
├── templates/                      # HTML templates (NEW)
│   ├── base.html                  # Base template with navigation
│   ├── index.html                 # Dashboard
│   ├── credentials.html           # Credentials management
│   ├── courses.html               # Course selection
│   ├── settings.html              # Settings configuration
│   ├── time_blocks.html           # Time block generator
│   └── logs.html                  # Log viewer
├── static/                         # Static assets (NEW)
│   ├── css/
│   │   └── style.css              # Responsive CSS styling
│   └── js/
│       └── main.js                # JavaScript utilities
├── canvas_notion_calendar_db_v1.py # Canvas/Notion API (existing)
├── time_blocker.py                 # Time block logic (existing)
├── schedule_grabber.py             # (existing)
└── requirements.txt                # Updated dependencies

OLD (no longer used):
├── CanvasAssignments.py           # PyQt6 desktop app (REPLACED)
```

## Running the Application

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 app.py

# Access in browser
# http://localhost:5000
```

### Production Deployment Options

#### Option 1: Local Server
Run on a home server or always-on computer, access from any device on your network.

#### Option 2: Cloud Hosting
Deploy to:
- **Heroku**: Free tier available, easy deployment
- **DigitalOcean**: App Platform or Droplet
- **AWS**: Elastic Beanstalk or EC2
- **Google Cloud**: App Engine
- **Azure**: App Service

#### Option 3: Docker Container
```bash
# Future: Create Dockerfile for containerization
docker build -t notionsync .
docker run -p 5000:5000 notionsync
```

## Technical Details

### Dependencies Changed
**Removed:**
- PyQt6
- qt-material
- (PyQt6-related packages)

**Added:**
- Flask (web framework)

**Kept:**
- requests (API calls)
- schedule (background tasks)
- keyring (secure storage)
- python-dateutil (date parsing)
- colorama (console output)

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Dashboard (redirects to /credentials if not configured) |
| `/credentials` | GET/POST | Manage API credentials |
| `/courses` | GET/POST | Select Canvas courses |
| `/settings` | GET/POST | Configure sync settings |
| `/time-blocks` | GET/POST | Generate time blocks |
| `/sync` | POST | Start sync operation |
| `/sync/status` | GET | Get current sync status (JSON) |
| `/logs` | GET | View sync logs |

### Security Considerations

1. **Credential Storage**: Still uses OS keyring (same as before)
2. **Session Management**: Flask sessions with random secret key
3. **HTTPS**: Should be used in production deployment
4. **Authentication**: Future enhancement for multi-user scenarios
5. **CORS**: Not enabled by default (local use)

## Browser Compatibility

### Tested and Supported
- ✅ Chrome/Chromium (latest)
- ✅ Firefox (latest)
- ✅ Safari (latest)
- ✅ Edge (latest)
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

### Requirements
- Modern browser with JavaScript enabled
- CSS Grid and Flexbox support
- Fetch API support

## Responsive Design

The interface adapts to different screen sizes:

- **Desktop (>768px)**: Full navigation, multi-column layouts
- **Tablet (768px)**: Stacked layouts, touch-friendly controls
- **Mobile (<768px)**: Single column, full-width buttons, optimized navigation

## Migration Guide

### For End Users
1. Uninstall PyQt6 if desired: `pip uninstall PyQt6 qt-material`
2. Install new requirements: `pip install -r requirements.txt`
3. Run the new app: `python3 app.py`
4. Access in browser: `http://localhost:5000`
5. Your existing credentials and settings will work automatically!

### For Developers
- Original PyQt6 code preserved in `CanvasAssignments.py`
- Can reference for feature parity checks
- All business logic modules (`canvas_notion_calendar_db_v1.py`, `time_blocker.py`) unchanged
- Easy to extend with new web features

## Future Enhancements

### Short Term
- [ ] Implement scheduler/daemon mode for web version
- [ ] Add mobile app icons and PWA support
- [ ] Improve mobile UI optimization

### Medium Term
- [ ] Multi-user authentication
- [ ] Docker containerization
- [ ] One-click deployment scripts
- [ ] Progressive Web App (PWA) for offline support

### Long Term
- [ ] Mobile native apps (using web view)
- [ ] Real-time notifications
- [ ] Collaboration features
- [ ] Advanced scheduling algorithms

## Conclusion

The migration from PyQt6 to a web-based interface makes NotionSync truly cross-platform and accessible from any device. The web approach is:

- **More accessible**: Works on phones, tablets, and all computers
- **Easier to use**: No installation required
- **Easier to maintain**: Standard web technologies
- **More flexible**: Can be self-hosted or cloud-deployed
- **Future-proof**: Web standards evolve continuously

This change addresses the user's requirement for a solution that works on "all devices" while maintaining all existing functionality and data compatibility.
