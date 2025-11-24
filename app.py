"""
NotionSync Web Application
--------------------------
Flask-based web interface for NotionSync - Canvas to Notion synchronization.
This replaces the PyQt6 desktop UI with a web interface accessible from any device.
"""

import sys
import os
import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import keyring
import schedule

from canvas_notion_calendar_db_v1 import (
    get_canvas_assignments,
    add_to_notion,
    ensure_database_properties,
    get_canvas_courses,
    get_notion_database_name,
    add_schedule_blocks_to_database,
)
from time_blocker import schedule_blocks

# --- Application Setup ---
APP_NAME = "NotionSync"

def get_safe_paths():
    """Returns application's data and log paths in a standard, safe location."""
    if sys.platform == "darwin":
        app_support_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', APP_NAME)
    elif sys.platform == "win32":
        app_support_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_NAME)
    else:
        app_support_dir = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)
    os.makedirs(app_support_dir, exist_ok=True)
    return {
        "credentials": os.path.join(app_support_dir, "credentials.json"),
        "log": os.path.join(app_support_dir, 'sync_log.txt')
    }

SAFE_PATHS = get_safe_paths()
credentials_file_path = SAFE_PATHS['credentials']
log_file_path = SAFE_PATHS['log']

# Flask app setup
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management

# Global variables for sync status
sync_status = {
    'running': False,
    'progress': '',
    'log': []
}

# --- Credential Management Functions ---

def load_credentials():
    """Load credentials from file and keyring."""
    if not os.path.exists(credentials_file_path):
        return {}
    
    with open(credentials_file_path, 'r') as f:
        creds = json.load(f)
    
    # Load sensitive data from keyring
    try:
        canvas_key = keyring.get_password(APP_NAME, "canvas_api_key")
        notion_key = keyring.get_password(APP_NAME, "notion_api_key")
        if canvas_key:
            creds['canvas_api_key'] = canvas_key
        if notion_key:
            creds['notion_api_key'] = notion_key
    except Exception as e:
        print(f"Error loading from keyring: {e}")
    
    return creds

def save_credentials(canvas_key, canvas_url, notion_key, notion_db_id):
    """Save credentials to file and keyring."""
    # Save sensitive keys to keyring
    try:
        if canvas_key:
            keyring.set_password(APP_NAME, "canvas_api_key", canvas_key)
        if notion_key:
            keyring.set_password(APP_NAME, "notion_api_key", notion_key)
    except Exception as e:
        print(f"Error saving to keyring: {e}")
        return False
    
    # Save non-sensitive data to file
    creds = {}
    if os.path.exists(credentials_file_path):
        with open(credentials_file_path, 'r') as f:
            creds = json.load(f)
    
    creds['canvas_base_url'] = canvas_url
    creds['notion_database_id'] = notion_db_id
    
    with open(credentials_file_path, 'w') as f:
        json.dump(creds, f, indent=2)
    
    return True

def get_config():
    """Get configuration settings."""
    if not os.path.exists(credentials_file_path):
        return {}
    
    with open(credentials_file_path, 'r') as f:
        return json.load(f)

def save_config(config):
    """Save configuration settings."""
    with open(credentials_file_path, 'w') as f:
        json.dump(config, f, indent=2)

# --- Sync Functions ---

def run_sync(status_callback=None):
    """Execute the sync operation."""
    global sync_status
    
    try:
        sync_status['running'] = True
        sync_status['progress'] = 'Starting sync...'
        sync_status['log'] = []
        
        creds = load_credentials()
        
        if not all([creds.get('canvas_api_key'), creds.get('canvas_base_url'),
                   creds.get('notion_api_key'), creds.get('notion_database_id')]):
            sync_status['progress'] = 'Error: Missing credentials'
            sync_status['running'] = False
            return
        
        # Update status
        def update_status(msg):
            sync_status['progress'] = msg
            sync_status['log'].append(f"{datetime.now().strftime('%H:%M:%S')} - {msg}")
            if status_callback:
                status_callback(msg)
        
        update_status("Fetching Canvas assignments...")
        
        config = get_config()
        selected_courses = config.get('selected_courses', [])
        buckets = config.get('buckets', ['past', 'undated', 'upcoming', 'future', 'ungraded'])
        
        assignments = get_canvas_assignments(
            creds['canvas_api_key'],
            creds['canvas_base_url'],
            selected_courses,
            buckets,
            update_status
        )
        
        update_status(f"Found {len(assignments)} assignments")
        
        update_status("Ensuring Notion database properties...")
        ensure_database_properties(
            creds['notion_api_key'],
            creds['notion_database_id'],
            update_status
        )
        
        update_status("Adding assignments to Notion...")
        add_to_notion(
            creds['notion_api_key'],
            creds['notion_database_id'],
            assignments,
            update_status
        )
        
        update_status("Sync completed successfully!")
        
        # Mark first sync complete
        config['first_sync_complete'] = True
        save_config(config)
        
    except Exception as e:
        sync_status['progress'] = f'Error: {str(e)}'
        sync_status['log'].append(f"ERROR: {str(e)}")
    finally:
        sync_status['running'] = False

# --- Routes ---

@app.route('/')
def index():
    """Main page - dashboard."""
    creds = load_credentials()
    has_credentials = all([
        creds.get('canvas_api_key'),
        creds.get('canvas_base_url'),
        creds.get('notion_api_key'),
        creds.get('notion_database_id')
    ])
    
    if not has_credentials:
        return redirect(url_for('credentials'))
    
    return render_template('index.html', creds=creds)

@app.route('/credentials', methods=['GET', 'POST'])
def credentials():
    """Credentials management page."""
    if request.method == 'POST':
        canvas_key = request.form.get('canvas_api_key')
        canvas_url = request.form.get('canvas_base_url', 'https://canvas.instructure.com/api/v1')
        notion_key = request.form.get('notion_api_key')
        notion_db_id = request.form.get('notion_database_id')
        
        if save_credentials(canvas_key, canvas_url, notion_key, notion_db_id):
            return redirect(url_for('index'))
        else:
            return render_template('credentials.html', error='Failed to save credentials')
    
    creds = load_credentials()
    return render_template('credentials.html', creds=creds)

@app.route('/sync', methods=['POST'])
def sync():
    """Start a sync operation."""
    if sync_status['running']:
        return jsonify({'error': 'Sync already running'}), 400
    
    # Run sync in background thread
    thread = threading.Thread(target=run_sync)
    thread.daemon = True
    thread.start()
    
    return jsonify({'status': 'started'})

@app.route('/sync/status')
def sync_status_endpoint():
    """Get current sync status."""
    return jsonify(sync_status)

@app.route('/courses', methods=['GET', 'POST'])
def courses():
    """Course selection page."""
    if request.method == 'POST':
        selected = request.form.getlist('courses')
        config = get_config()
        config['selected_courses'] = [int(c) for c in selected]
        save_config(config)
        return redirect(url_for('index'))
    
    creds = load_credentials()
    if not creds.get('canvas_api_key') or not creds.get('canvas_base_url'):
        return redirect(url_for('credentials'))
    
    try:
        all_courses = get_canvas_courses(
            creds['canvas_api_key'],
            creds['canvas_base_url']
        )
        config = get_config()
        selected_courses = config.get('selected_courses', [])
        
        return render_template('courses.html', 
                             courses=all_courses,
                             selected=selected_courses)
    except Exception as e:
        return render_template('courses.html', 
                             error=f'Failed to load courses: {str(e)}',
                             courses=[],
                             selected=[])

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page."""
    if request.method == 'POST':
        config = get_config()
        
        # Update buckets
        buckets = request.form.getlist('buckets')
        if buckets:
            config['buckets'] = buckets
        
        # Update scheduler settings
        scheduler_enabled = request.form.get('scheduler_enabled') == 'on'
        config['scheduler_enabled'] = scheduler_enabled
        
        if scheduler_enabled:
            sync_time = request.form.get('sync_time')
            if sync_time:
                config['sync_time'] = sync_time
        
        save_config(config)
        return redirect(url_for('index'))
    
    config = get_config()
    all_buckets = ['past', 'undated', 'upcoming', 'future', 'ungraded']
    selected_buckets = config.get('buckets', all_buckets)
    
    return render_template('settings.html',
                         all_buckets=all_buckets,
                         selected_buckets=selected_buckets,
                         config=config)

@app.route('/time-blocks', methods=['GET', 'POST'])
def time_blocks():
    """Time block generator page."""
    if request.method == 'POST':
        # Get form data
        block_length = int(request.form.get('block_length', 60))
        daily_max = int(request.form.get('daily_max', 480))
        availability_json = request.form.get('availability', '{}')
        export_to_notion = request.form.get('export_to_notion') == 'on'
        
        try:
            creds = load_credentials()
            
            # Get assignments
            config = get_config()
            selected_courses = config.get('selected_courses', [])
            buckets = config.get('buckets', ['upcoming', 'future'])
            
            assignments = get_canvas_assignments(
                creds['canvas_api_key'],
                creds['canvas_base_url'],
                selected_courses,
                buckets
            )
            
            # Generate time blocks
            availability = json.loads(availability_json) if availability_json and availability_json != '{}' else None
            blocks = schedule_blocks(
                assignments,
                availability,
                block_minutes=block_length,
                daily_max_minutes=daily_max
            )
            
            # Export to Notion if requested
            if export_to_notion:
                add_schedule_blocks_to_database(
                    creds['notion_api_key'],
                    creds['notion_database_id'],
                    blocks
                )
                message = f"Generated {len(blocks)} time blocks and exported to Notion!"
            else:
                message = f"Generated {len(blocks)} time blocks (preview only)"
            
            return render_template('time_blocks.html',
                                 blocks=blocks,
                                 message=message)
        except Exception as e:
            return render_template('time_blocks.html',
                                 error=f'Error: {str(e)}')
    
    return render_template('time_blocks.html')

@app.route('/logs')
def logs():
    """View sync logs."""
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            log_content = f.read()
    else:
        log_content = "No logs available"
    
    return render_template('logs.html', log_content=log_content)

# --- Main ---

if __name__ == '__main__':
    # Check for command-line arguments
    if '--daemon' in sys.argv:
        print("Daemon mode not yet implemented for web version")
        sys.exit(1)
    elif '--background' in sys.argv:
        print("Running background sync...")
        run_sync()
        sys.exit(0)
    else:
        # Run the web server
        port = int(os.environ.get('PORT', 5000))
        print(f"\n{'='*60}")
        print(f"NotionSync Web Interface")
        print(f"{'='*60}")
        print(f"Access the application at: http://localhost:{port}")
        print(f"Press CTRL+C to stop the server")
        print(f"{'='*60}\n")
        
        app.run(host='0.0.0.0', port=port, debug=True)
