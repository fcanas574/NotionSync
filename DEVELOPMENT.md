# NotionSync Development Guide

## Quick Start

### Running the Web Application
```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python3 app.py

# Access in browser
http://localhost:5000
```

### Environment Variables (Optional)
```bash
export SECRET_KEY="your-random-secret-key"  # For production
export FLASK_HOST="127.0.0.1"               # Local only (default: 0.0.0.0)
export FLASK_ENV="development"              # Enable debug mode
export PORT=5000                            # Server port (default: 5000)
```

## Project Structure

### Active Codebase (Web Interface)
```
app.py                           # Main Flask application
templates/                       # HTML templates
  ├── base.html                 # Base template
  ├── index.html                # Dashboard
  ├── credentials.html          # Credentials management
  ├── courses.html              # Course selection
  ├── settings.html             # Settings
  ├── time_blocks.html          # Time block generator
  └── logs.html                 # Log viewer
static/
  ├── css/style.css            # Responsive CSS
  └── js/main.js               # JavaScript utilities
```

### Backend Modules (Shared)
```
canvas_notion_calendar_db_v1.py  # Canvas/Notion API integration
time_blocker.py                  # Time block generation logic
schedule_grabber.py              # Schedule utilities
```

### Legacy Code (No Longer Used)
```
CanvasAssignments.py             # Old PyQt6 desktop app (DEPRECATED)
```

## Key Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Dashboard (redirects to credentials if not configured) |
| `/credentials` | GET/POST | Manage API credentials |
| `/courses` | GET/POST | Select Canvas courses |
| `/settings` | GET/POST | Configure sync settings |
| `/time-blocks` | GET/POST | Generate time blocks |
| `/sync` | POST | Start sync operation |
| `/sync/status` | GET | Get current sync status (JSON API) |
| `/logs` | GET | View sync logs |

## Testing

### Test All Routes
```bash
cd /home/runner/work/NotionSync/NotionSync
python3 << 'EOF'
from app import app
import threading, time, urllib.request

def run_server():
    app.run(host='127.0.0.1', port=5002, debug=False, use_reloader=False)

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(3)

pages = ['/', '/credentials', '/courses', '/settings', '/time-blocks', '/logs']
for page in pages:
    try:
        url = f'http://localhost:5002{page}'
        response = urllib.request.urlopen(url, timeout=5)
        print(f'✓ {page:20s} - Status {response.getcode()}')
    except Exception as e:
        print(f'✗ {page:20s} - Error: {str(e)[:40]}')
EOF
```

## Data Storage

### Configuration
- **Location**: OS-specific app support directory
  - macOS: `~/Library/Application Support/NotionSync/`
  - Windows: `%APPDATA%/NotionSync/`
  - Linux: `~/.config/NotionSync/`
- **Files**:
  - `credentials.json` - Non-sensitive configuration
  - `sync_log.txt` - Sync operation logs

### Secure Credentials
- Stored in OS keyring via `keyring` library
- Keys: `canvas_api_key`, `notion_api_key`
- Service name: `NotionSync`

## Development Tips

1. **Use development mode** for auto-reload:
   ```bash
   export FLASK_ENV=development
   python3 app.py
   ```

2. **Test on mobile device**:
   - Find your computer's IP: `ifconfig` or `ipconfig`
   - Access from phone: `http://192.168.1.XXX:5000`

3. **Check logs**:
   ```bash
   # Application logs
   cat ~/Library/Application\ Support/NotionSync/sync_log.txt  # macOS
   
   # Flask logs in terminal
   python3 app.py
   ```

4. **Clear credentials** (for testing):
   ```bash
   rm ~/Library/Application\ Support/NotionSync/credentials.json  # macOS
   # Then use keyring to remove secrets:
   python3 -c "import keyring; keyring.delete_password('NotionSync', 'canvas_api_key')"
   python3 -c "import keyring; keyring.delete_password('NotionSync', 'notion_api_key')"
   ```

## Common Issues

### Port Already in Use
```bash
# Find and kill process on port 5000
lsof -ti:5000 | xargs kill -9

# Or use a different port
export PORT=5001
python3 app.py
```

### Cannot Access from Other Devices
```bash
# Make sure FLASK_HOST allows network access
export FLASK_HOST="0.0.0.0"
python3 app.py
```

### Session Lost on Restart
```bash
# Set a persistent secret key
export SECRET_KEY="your-static-secret-key-here"
python3 app.py
```

## Deployment

### Local Network
1. Run on always-on computer
2. Access from any device on the network

### Cloud Platforms
- **Heroku**: `git push heroku main`
- **DigitalOcean**: App Platform or Droplet
- **AWS**: Elastic Beanstalk
- **Google Cloud**: App Engine

### Production Server (Gunicorn)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Contributing

1. The web interface is the active codebase
2. Don't modify `CanvasAssignments.py` (deprecated)
3. Reuse backend modules (`canvas_notion_calendar_db_v1.py`, `time_blocker.py`)
4. Keep templates responsive for mobile devices
5. Test on multiple browsers and screen sizes

## Documentation

- `README.md` - User documentation
- `WEB_MIGRATION.md` - Migration details from PyQt6
- `DEVELOPMENT.md` - This file
