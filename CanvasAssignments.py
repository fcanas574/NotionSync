import sys
import os
from datetime import datetime
import json
import time
import schedule
import re # Import regex for parsing status messages
import locale # --- NEW: For language detection ---
import keyring # --- NEW: For secure credential storage ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QDialog,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QSystemTrayIcon, QMenu, QTimeEdit, QCheckBox, QTabWidget, QTabBar,
    QComboBox, QGroupBox # --- NEW: Added QComboBox and QGroupBox ---
)
from PyQt6.QtGui import QIcon, QAction, QFontDatabase, QPixmap, QPainter, QColor, QPolygonF
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTime, QPointF, QSize, QTimer

# --- MODIFIED: Import the new function ---
from canvas_notion_calendar_db_v1 import (
    get_canvas_assignments,
    add_to_notion,
    ensure_database_properties,
    get_canvas_courses,
    get_notion_database_name,
    add_schedule_blocks_to_database,
)

# Module purpose:
# This file implements the PyQt6 UI and application glue for NotionSync.
# - Collects and persists user settings (in a per-user config path).
# - Stores API keys securely in the OS keyring.
# - Starts background worker threads for network operations so the UI stays
#   responsive. The network-heavy logic lives in canvas_notion_calendar_db_v1.py.
# - Provides system tray integration and scheduled sync support.

# --- PATHING & RESOURCE HELPERS (NEW) ---
APP_NAME = "NotionSync"

def resource_path(relative_path):
    """Return absolute path to a resource file.

    Works in two modes:
    - Development: resolves relative to this file's directory.
    - Bundled (PyInstaller): resolves via the `_MEIPASS` temporary folder.

    Use this helper whenever loading images, fonts or other files packaged
    with the application so paths remain correct across environments.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # For development environment
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def get_safe_paths():
    """Returns application's data and log paths in a standard, safe location."""
    if sys.platform == "darwin":
        app_support_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', APP_NAME)
    elif sys.platform == "win32":
        app_support_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_NAME)
    else: # Linux/Other
        app_support_dir = os.path.join(os.path.expanduser('~'), '.config', APP_NAME)
    
    # Ensure the directory exists
    os.makedirs(app_support_dir, exist_ok=True)
    
    return {
        "credentials": os.path.join(app_support_dir, "credentials.json"),
        "log": os.path.join(app_support_dir, 'sync_log.txt')
    }

SAFE_PATHS = get_safe_paths()
credentials_file_path = SAFE_PATHS['credentials']
log_file_path_global = SAFE_PATHS['log'] 
# --- END OF PATHING & RESOURCE HELPERS ---


# --- Language Detection and Translation Strings (Unchanged) ---
try:
    locale.setlocale(locale.LC_ALL, '')
    lang_code_full = locale.getlocale(locale.LC_CTYPE)[0]
    if lang_code_full:
        LANG_CODE = lang_code_full[:2] 
        if LANG_CODE not in ['en', 'es']: LANG_CODE = 'en'
    else: LANG_CODE = 'en'
except Exception: LANG_CODE = 'en'

def load_html_resource(filename):
    path = resource_path(filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return f"<h1>Error: {filename} not found</h1>"

# --- HELP_HTML_EN (Loaded from file) ---
HELP_HTML_EN = load_html_resource("help_en.html")

# --- HELP_HTML_ES (Loaded from file) ---
HELP_HTML_ES = load_html_resource("help_es.html")

# --- TRANSLATIONS (Unchanged) ---
TRANSLATIONS = {
    'en': {
        'window_title': "Canvas to Notion Sync",
        'canvas_key_label': "Canvas API Key:", 'canvas_key_placeholder': "Enter Canvas API Key",
        'notion_key_label': "Notion API Key:", 'notion_key_placeholder': "Enter Notion API Key",
        'notion_db_label': "Notion Database ID:", 'notion_db_placeholder': "Enter Notion Database ID or URL",
        'help_tooltip': "Help: How to get API Keys", 'run_sync_button': "Run Manual Sync",
        'tab_credentials': "Credentials & Sync", 'tab_scheduler': "Scheduler",
        'scheduler_label': "Set daily sync time (24-hour format):",
        'startup_checkbox': "Start automatically on login",
        'sync_error_all_fields': "Error: All fields are required. Click the help button for setup instructions.",
        'tray_tooltip': "Canvas to Notion Sync", 'tray_run_sync': "Run Manual Sync",
        'tray_show_window': "Show Window", 'tray_quit': "Quit",
        'help_title': "API Key Setup Guide", 'help_close': "Close",
        'help_switch_button': "Ver en Español", 'help_html': HELP_HTML_EN,
        'easter_egg_title': "Special Thanks!", 'easter_egg_message': "Thank you DOer for using the app",
        # --- NEW TRANSLATIONS ---
        'canvas_url_label': "Canvas URL:",
        'use_default_url': "Use Default Institution (Key Institute)",
        'custom_url_placeholder': "https://canvas.instructure.com/api/v1",
        'sync_scope_label': "Sync Scope (Buckets):",
        'bucket_past': "Past", 'bucket_undated': "Undated", 'bucket_upcoming': "Upcoming",
        'bucket_future': "Future", 'bucket_ungraded': "Ungraded",
        'notification_success_title': "Sync Successful",
        'notification_success_msg': "Canvas assignments synced to Notion.",
        'notification_fail_title': "Sync Failed",
        'notification_fail_msg': "Error syncing assignments. Check log."
    },
    'es': {
        'window_title': "Sincronización de Canvas a Notion",
        'canvas_key_label': "Clave API de Canvas:", 'canvas_key_placeholder': "Ingresa la Clave API de Canvas",
        'notion_key_label': "Clave API de Notion:", 'notion_key_placeholder': "Ingresa la Clave API de Notion",
        'notion_db_label': "ID de Base de Datos de Notion:", 'notion_db_placeholder': "Ingresa el ID o la URL de la Base de Datos de Notion",
        'help_tooltip': "Ayuda: Cómo obtener Claves API", 'run_sync_button': "Ejecutar Sincronización Manual",
        'tab_credentials': "Credenciales y Sincronización", 'tab_scheduler': "Programador",
        'scheduler_label': "Establecer hora de sincronización diaria (formato 24h):",
        'startup_checkbox': "Iniciar automáticamente al iniciar sesión",
        'sync_error_all_fields': "Error: Todos los campos son requeridos. Haz clic en el botón de ayuda para instrucciones.",
        'tray_tooltip': "Sincronización de Canvas a Notion", 'tray_run_sync': "Ejecutar Sincronización Manual",
        'tray_show_window': "Mostrar Ventana", 'tray_quit': "Salir",
        'help_title': "Guía de Configuración de Claves API", 'help_close': "Cerrar",
        'help_switch_button': "View in English", 'help_html': HELP_HTML_ES,
        'easter_egg_title': "¡Gracias Especiales!", 'easter_egg_message': "Gracias DOer por usar la app",
        # --- NEW TRANSLATIONS ---
        'canvas_url_label': "URL de Canvas:",
        'use_default_url': "Usar Institución Predeterminada (Key Institute)",
        'custom_url_placeholder': "https://canvas.instructure.com/api/v1",
        'sync_scope_label': "Alcance de Sincronización (Categorías):",
        'bucket_past': "Pasado", 'bucket_undated': "Sin Fecha", 'bucket_upcoming': "Próximo",
        'bucket_future': "Futuro", 'bucket_ungraded': "Sin Calificar",
        'notification_success_title': "Sincronización Exitosa",
        'notification_success_msg': "Asignaciones de Canvas sincronizadas con Notion.",
        'notification_fail_title': "Sincronización Fallida",
        'notification_fail_msg': "Error al sincronizar. Revisa el registro."
    }
}
T = TRANSLATIONS[LANG_CODE]

# --- QSS Stylesheet (Unchanged) ---
# Application-wide styles (QSS). Keep this separate so the UI theme is
# consistently applied whether the app is run from source or packaged.
MODERN_QSS = """
QWidget {
    background-color: #2b2b2b; color: #f0f0f0;
    font-family: 'Figtree', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 14px;
}
QTabWidget::pane { border: 1px solid #555; border-top: none; }
QTabBar::tab {
    background: #2b2b2b; border: 1px solid #555; border-bottom: none;
    padding: 8px 15px; border-top-left-radius: 4px; border-top-right-radius: 4px;
}
QTabBar::tab:selected { background: #3c3f41; border-color: #555; }
QTabBar::tab:!selected { margin-top: 2px; }
QLabel { background-color: transparent; }
QLineEdit { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; padding: 6px; }
QLineEdit:focus { border: 1px solid #0078d7; }
QPushButton { background-color: #0078d7; color: white; font-weight: bold; border: none; border-radius: 4px; padding: 8px 16px; }
QPushButton:hover { background-color: #005a9e; }
QPushButton:disabled { background-color: #4f4f4f; color: #999; }
QPushButton#HelpButton {
    background-color: #4a4a4a; font-weight: bold; font-size: 16px; color: #f0f0f0;
    border-radius: 15px; padding: 0px; text-align: center; border: none;
}
QPushButton#HelpButton:hover { background-color: #5a5a5a; }
QTextEdit { background-color: #252526; border: 1px solid #555; border-radius: 4px; padding: 4px; }
QProgressBar { border: 1px solid #555; border-radius: 4px; text-align: center; color: #f0f0f0; }
QProgressBar::chunk { background-color: #0078d7; border-radius: 3px; margin: 1px; }
QMenu { background-color: #3c3f41; border: 1px solid #555; }
QMenu::item { padding: 8px 20px; }
QMenu::item:selected { background-color: #0078d7; }
QMenu::separator { height: 1px; background: #555; margin: 4px 0px; }
QTimeEdit { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; padding: 4px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; border-radius: 3px; }
QCheckBox::indicator:unchecked { background-color: #3c3f41; }
QCheckBox::indicator:checked { background-color: transparent; border: 1px solid #0078d7; image: url(icon:checkmark.png); }
QTextEdit#HelpText { background-color: #2b2b2b; border: none; padding: 10px; }
"""

# If a bundled `check.png` exists, update the QSS to reference its absolute path
_check_img_path = resource_path("check.png")
_check_img_path = _check_img_path.replace("\\", "/")
# Replace only the image URL portion so background/border edits remain intact
MODERN_QSS = MODERN_QSS.replace(
    "image: url(icon:checkmark.png);",
    "image: url(" + _check_img_path + ");"
)

# --- EasterEggPopup Class (MODIFIED for resource_path) ---
class EasterEggPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T['easter_egg_title']) 
        self.setFixedSize(300, 300) 
        self.setModal(True)
        layout = QVBoxLayout(self)
        message_label = QLabel(T['easter_egg_message'])
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(message_label)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # --- FIX: Use resource_path for logo ---
        image_path = resource_path("doer_logo.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(scaled_pixmap)
        else:
            image_label.setText("Image not found: doer_logo.png")
            image_label.setStyleSheet("color: red; font-size: 12px;")
        layout.addWidget(image_label)

# --- EasterEggTabBar Class (Unchanged) ---
class EasterEggTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scheduler_clicks = 0
        self._last_click_time = 0

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        tab_index = self.tabAt(event.pos())
        if tab_index == 1:
            current_time = time.time()
            if current_time - self._last_click_time > 3.0:
                self._scheduler_clicks = 1
            else:
                self._scheduler_clicks += 1
            self._last_click_time = current_time
            if self._scheduler_clicks >= 5:
                self._scheduler_clicks = 0 
                popup = EasterEggPopup(self.window())
                popup.exec()

# --- HelpDialog Class (Unchanged) ---
class HelpDialog(QDialog):
    def __init__(self, lang='en', parent=None):
        super().__init__(parent)
        self.setWindowTitle(T['help_title']) 
        self.setModal(True)
        self.setMinimumSize(600, 500)
        self.current_lang = lang 
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("HelpText") 
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        button_layout = QHBoxLayout()
        self.lang_toggle_button = QPushButton()
        self.lang_toggle_button.clicked.connect(self._toggle_language)
        button_layout.addWidget(self.lang_toggle_button)
        button_layout.addStretch() 
        close_button = QPushButton(T['help_close']) 
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        self._update_content()

    def _update_content(self):
        if self.current_lang == 'en':
            self.text_edit.setHtml(HELP_HTML_EN)
            self.lang_toggle_button.setText(TRANSLATIONS['en']['help_switch_button'])
        else: # 'es'
            self.text_edit.setHtml(HELP_HTML_ES)
            self.lang_toggle_button.setText(TRANSLATIONS['es']['help_switch_button'])

    def _toggle_language(self):
        self.current_lang = 'es' if self.current_lang == 'en' else 'en'
        self._update_content()


# --- CourseLoaderThread (module-level to avoid Qt meta-object issues) ---
class CourseLoaderThread(QThread):
    finished_loading = pyqtSignal(object)

    def __init__(self, key=None, base=None, parent=None):
        super().__init__(parent)
        self.key = key
        self.base = base

    def run(self):
        try:
            courses = get_canvas_courses(self.key, self.base)
        except Exception:
            courses = []
        self.finished_loading.emit(courses)


# --- DatabaseNameLoaderThread (fetches database title asynchronously) ---
class DatabaseNameLoaderThread(QThread):
    finished = pyqtSignal(object)

    def __init__(self, notion_key=None, database_id=None, parent=None):
        super().__init__(parent)
        self.notion_key = notion_key
        self.database_id = database_id

    def run(self):
        try:
            name = get_notion_database_name(self.notion_key, self.database_id)
        except Exception:
            name = None
        self.finished.emit(name)


# --- TimeBlockThread: generate blocks in background to avoid UI freeze ---
class TimeBlockThread(QThread):
    finished = pyqtSignal(object, object)  # (blocks, message)

    def __init__(self, canvas_key, base_url, buckets, selected_course_ids, block_minutes, daily_max, availability=None, notion_key=None, notion_db_id=None, export=False, parent=None):
        super().__init__(parent)
        self.canvas_key = canvas_key
        self.base_url = base_url
        self.buckets = buckets
        self.selected_course_ids = selected_course_ids
        self.block_minutes = block_minutes
        self.daily_max = daily_max
        self.availability = availability
        self.notion_key = notion_key
        self.notion_db_id = notion_db_id
        self.export = export

    def run(self):
        try:
            # Fetch assignments using existing helper
            assignments_raw = get_canvas_assignments(self.canvas_key, self.base_url, self.buckets, self.selected_course_ids, None)

            # Normalize assignments to the format expected by schedule_blocks
            normalized = []
            for a in assignments_raw:
                due = a.get('due_at') or a.get('lock_at') or a.get('created_at')
                due_date = None
                if due:
                    try:
                        due_date = due.split('T')[0]
                    except Exception:
                        due_date = None
                normalized.append({
                    'id': a.get('id'),
                    'name': a.get('name'),
                    'due_at': due,
                    'due_date': due_date,
                    'course_name': a.get('course_name'),
                    'description': a.get('description'),
                    'html_url': a.get('html_url')
                })

            # Import scheduler function locally to avoid top-level dependency
            from time_blocker import schedule_blocks

            availability = self.availability or {'weekly': {str(i): [{'start': '18:00', 'end': '21:00'}] for i in range(7)}}
            blocks = schedule_blocks(normalized, availability, block_minutes=self.block_minutes, daily_max_minutes=self.daily_max)

            # If export requested, push to Notion (must have keys)
            if self.export:
                if not (self.notion_key and self.notion_db_id):
                    self.finished.emit(None, 'Export requested but Notion key or database id missing')
                    return
                # Use helper to add blocks
                created = add_schedule_blocks_to_database(self.notion_key, self.notion_db_id, blocks, status_callback=None)
                msg = f'Exported {len(created)} blocks to Notion database {self.notion_db_id}'
                self.finished.emit(blocks, msg)
                return

            self.finished.emit(blocks, f'Planned {len(blocks)} blocks (dry run)')

        except Exception as e:
            self.finished.emit(None, f'Error generating blocks: {e}')


# --- SyncThread ---
# Long-running worker executed in a separate QThread to perform a full
# synchronization cycle. Signals are used to report status/progress back to
# the UI so the main thread can remain responsive.
class SyncThread(QThread):
    update_status = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    # --- NEW: Signal for success ---
    sync_succeeded = pyqtSignal() 
    sync_failed = pyqtSignal() # --- NEW: Signal for failure ---
    
    # --- MODIFIED: Accept first_sync_complete flag ---
    def __init__(self, canvas_key: str, notion_key: str, notion_db_id: str, first_sync_complete: bool, base_url: str, buckets: list, selected_course_ids=None):
        super().__init__()
        self.canvas_key = canvas_key
        self.notion_key = notion_key
        self.notion_db_id = notion_db_id
        self.first_sync_complete = first_sync_complete # Store the flag
        self.base_url = base_url
        self.buckets = buckets
        self.selected_course_ids = selected_course_ids

    def run(self):
        try:
            self.update_status.emit("Starting sync process...")
            self.update_progress.emit(5)
            
            # --- FIX: Call schema check and get date_property_name ---
            self.update_status.emit("Verifying Notion database properties...")
            schema_ok, date_property_name = ensure_database_properties(self.notion_key, self.notion_db_id, self.update_status.emit)
            
            if not schema_ok:
                self.update_status.emit("❌ Database setup failed. Aborting sync.")
                self.update_status.emit("   Check permissions, Database ID, and API version.")
                self.update_progress.emit(0)
                self.sync_failed.emit()
                return # Stop the sync
            
            self.update_status.emit(f"   Using date property: '{date_property_name}'")
            # --- END OF FIX ---
            
            self.update_progress.emit(10)
            self.update_status.emit("Fetching assignments from Canvas (concurrently)...")
            
            # --- MODIFIED: Pass base_url and buckets ---
            assignments = get_canvas_assignments(self.canvas_key, self.base_url, self.buckets, self.selected_course_ids, self.update_status.emit)
            if not assignments:
                self.update_status.emit("No new assignments found or Canvas fetch failed.")
                self.update_progress.emit(100)
                self.sync_succeeded.emit() # Consider empty fetch as success? Or maybe just done.
                return
            self.update_progress.emit(40)

            def status_and_progress_callback(message):
                self.update_status.emit(message)
                match = re.search(r"Processing (\d+)/(\d+)", message)
                if match:
                    current_item, total_items = int(match.group(1)), int(match.group(2))
                    progress = 45 + int((current_item / total_items) * 50)
                    self.update_progress.emit(progress)
                elif "Fetching existing entries" in message:
                    self.update_progress.emit(45)

            # --- MODIFIED: Pass is_first_sync flag ---
            # We pass `not self.first_sync_complete` because if the flag is False (not complete),
            # then is_first_sync should be True.
            add_to_notion(
                self.notion_key, 
                self.notion_db_id, 
                assignments, 
                status_and_progress_callback, 
                date_property_name,
                is_first_sync=not self.first_sync_complete
            )
            
            self.update_status.emit("Sync completed successfully.")
            self.update_progress.emit(100)
            # --- NEW: Emit success signal ---
            self.sync_succeeded.emit()
            
        except Exception as e:
            self.update_status.emit(f"An unexpected error occurred during sync: {e}")
            self.update_progress.emit(0)
            self.sync_failed.emit()

# --- Main application class ---
# `NotionSyncApp` composes the entire GUI, wires widgets to settings,
# and coordinates background workers (course loader, DB name fetcher, sync).
# Keep UI code here; delegate API calls to canvas_notion_calendar_db_v1.py.
class NotionSyncApp(QWidget):
    def __init__(self):
        super().__init__()
        self.lang = LANG_CODE 
        self.setWindowTitle(T['window_title']); self.resize(640, 600) 
        # --- FIX: Use safe, global path ---
        self.credentials_file = credentials_file_path
        self.tray_icon = None # Will be assigned later
        self._setup_ui()
        self._load_settings()

    def closeEvent(self, event):
        event.ignore(); self.hide()

    def _save_settings(self, key, value):
        # Handle sensitive keys with keyring
        if key in ["canvas_key", "notion_key"]:
            if value:
                keyring.set_password(APP_NAME, key, value)
            else:
                try:
                    keyring.delete_password(APP_NAME, key)
                except keyring.errors.PasswordDeleteError:
                    pass
            return

        data = {}
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r') as f: data = json.load(f)
            except (json.JSONDecodeError, IOError): pass
        
        # Remove sensitive keys from json if they exist (migration)
        if "canvas_key" in data: del data["canvas_key"]
        if "notion_key" in data: del data["notion_key"]
        
        data[key] = value
        with open(self.credentials_file, 'w') as f: json.dump(data, f, indent=4)

    def _load_settings(self):
        # Load sensitive keys from keyring
        self.canvas_input.setText(keyring.get_password(APP_NAME, "canvas_key") or "")
        self.notion_key_input.setText(keyring.get_password(APP_NAME, "notion_key") or "")

        if not os.path.exists(self.credentials_file): return
        try:
            with open(self.credentials_file, 'r') as f: data = json.load(f)
            
            # Fallback for migration: check json if keyring is empty
            if not self.canvas_input.text() and "canvas_key" in data:
                self.canvas_input.setText(data["canvas_key"])
                # Migrate to keyring
                keyring.set_password(APP_NAME, "canvas_key", data["canvas_key"])
            
            if not self.notion_key_input.text() and "notion_key" in data:
                self.notion_key_input.setText(data["notion_key"])
                # Migrate to keyring
                keyring.set_password(APP_NAME, "notion_key", data["notion_key"])

            self.notion_db_input.setText(data.get("notion_db_id", ""))
            sync_time_str = data.get('sync_time', "23:59")
            h, m = map(int, sync_time_str.split(':'))
            self.time_edit.setTime(QTime(h, m))
            self.startup_checkbox.setChecked(is_startup_enabled())
            
            # Load Canvas URL settings
            self.use_default_url_cb.setChecked(data.get("use_default_url", True))
            self.canvas_url_input.setText(data.get("canvas_url", ""))
            self._toggle_canvas_url_input(self.use_default_url_cb.isChecked())
            
            # Load Buckets settings
            buckets = data.get("buckets", ["past", "undated", "upcoming", "future", "ungraded"])
            for bucket, cb in self.bucket_checkboxes.items():
                cb.setChecked(bucket in buckets)
            # Show warning if buckets is empty
            try:
                if not buckets:
                    self.scope_warning_label.setVisible(True)
                else:
                    self.scope_warning_label.setVisible(False)
            except Exception:
                pass

            # Load advanced toggle state and show/hide advanced UI
            show_advanced = data.get("show_advanced", False)
            try:
                self.advanced_toggle.setChecked(show_advanced)
                self._toggle_advanced(show_advanced)
            except Exception:
                pass

            # Update course summary label after loading settings
            try:
                self._update_course_summary()
            except Exception:
                pass

        except Exception: pass

    # --- NEW: Added for crash fix ---
    def _on_sync_finished(self):
        """Called when the sync thread is finished."""
        self.run_button.setEnabled(True)
        if hasattr(self, 'tray_run_action'):
            self.tray_run_action.setEnabled(True)
        if hasattr(self, 'tray_quit_action'):
            self.tray_quit_action.setEnabled(True)

    # --- NEW: Added for crash fix ---
    def set_tray_actions(self, run_action, quit_action):
        """Stores references to tray menu actions to control their state."""
        self.tray_run_action = run_action
        self.tray_quit_action = quit_action

    # --- NEW: Helper to read a single value ---
    def _load_settings_value(self, key, default=None):
        if not os.path.exists(self.credentials_file): 
            return default
        try:
            with open(self.credentials_file, 'r') as f: 
                data = json.load(f)
            return data.get(key, default)
        except Exception: 
            return default

    # --- NEW: Slot to mark first sync as done ---
    def _mark_first_sync_complete(self):
        # Only mark as complete if it wasn't already
        if not self._load_settings_value("first_sync_complete", False):
            self.status_output.append("Marking first sync as complete.")
            self._save_settings("first_sync_complete", True)

    def _on_sync_success(self):
        self._mark_first_sync_complete()
        if self.tray_icon:
            self.tray_icon.showMessage(T['notification_success_title'], T['notification_success_msg'], QSystemTrayIcon.MessageIcon.Information, 3000)

    def _on_load_courses(self):
        # Start a small thread to fetch courses and display a dialog for selection
        canvas_key = self.canvas_input.text().strip()
        if self.use_default_url_cb.isChecked():
            base_url = "https://keyinstitute.instructure.com/api/v1"
        else:
            base_url = self.canvas_url_input.text().strip()

        if not canvas_key or not base_url:
            self.status_output.append("Please provide Canvas API key and URL before loading courses.")
            return

        # Use a module-level QThread worker
        loader = CourseLoaderThread(key=canvas_key, base=base_url)
        # keep a reference so it isn't garbage-collected while running
        self.course_loader_thread = loader

        def on_loaded(courses):
            if not courses:
                self.status_output.append("No courses returned from Canvas or fetch failed.")
                return

            # Build dialog with checkboxes
            dlg = QDialog(self)
            dlg.setWindowTitle("Select Courses to Sync")
            dlg_layout = QVBoxLayout(dlg)
            scroll_layout = QVBoxLayout()
            checkbox_map = {}

            saved_selected = set(self._load_settings_value("selected_course_ids", []))

            for c in courses:
                cid = str(c.get('id'))
                name = c.get('name') or f"Course {cid}"
                cb = QCheckBox(name)
                cb.setChecked((not saved_selected) or (cid in saved_selected))
                checkbox_map[cid] = cb
                scroll_layout.addWidget(cb)

            dlg_layout.addLayout(scroll_layout)
            btn_layout = QHBoxLayout()
            save_btn = QPushButton("Save")
            cancel_btn = QPushButton("Cancel")
            btn_layout.addStretch()
            btn_layout.addWidget(cancel_btn)
            btn_layout.addWidget(save_btn)
            dlg_layout.addLayout(btn_layout)

            def on_save():
                selected = [cid for cid, cb in checkbox_map.items() if cb.isChecked()]
                self._save_settings('selected_course_ids', selected)
                self._update_course_summary()
                dlg.accept()

            save_btn.clicked.connect(on_save)
            cancel_btn.clicked.connect(dlg.reject)
            dlg.exec()

        loader.finished_loading.connect(on_loaded)
        loader.finished_loading.connect(lambda _: setattr(self, 'course_loader_thread', None))
        loader.start()

    def _on_sync_fail(self):
        if self.tray_icon:
            self.tray_icon.showMessage(T['notification_fail_title'], T['notification_fail_msg'], QSystemTrayIcon.MessageIcon.Warning, 3000)

    def _show_help_dialog(self):
        dialog = HelpDialog(lang=self.lang, parent=self) 
        dialog.exec()

    def _on_notion_input_changed(self, text):
        match = re.search(r"notion\.so/(?:[^/]+/)?([a-f0-9]{32})", text)
        if match:
            db_id = match.group(1)
            self.notion_db_input.textChanged.disconnect(self._on_notion_input_changed)
            self.notion_db_input.setText(db_id)
            self.notion_db_input.textChanged.connect(self._on_notion_input_changed)
            text = db_id
        
        # Visual validation
        if re.fullmatch(r"[a-f0-9]{32}", text):
            self.notion_db_input.setStyleSheet("border: 1px solid #00ff00;")
            # Start a background lookup for the database title
            notion_key = self.notion_key_input.text().strip() or keyring.get_password(APP_NAME, "notion_key") or ""
            if notion_key:
                loader = DatabaseNameLoaderThread(notion_key=notion_key, database_id=text)
                self.db_name_thread = loader
                def _on_db_name(name):
                    try:
                        if name:
                            self.notion_db_name_label.setText(f"Database: {name}")
                            self.notion_db_name_label.setStyleSheet("color: #a9ffb1; font-size: 12px; margin-top: 4px;")
                        else:
                            self.notion_db_name_label.setText("Database: (not found or inaccessible)")
                            self.notion_db_name_label.setStyleSheet("color: #ffb1b1; font-size: 12px; margin-top: 4px;")
                    except Exception:
                        pass
                    finally:
                        try:
                            self.db_name_thread = None
                        except Exception:
                            pass
                loader.finished.connect(_on_db_name)
                loader.start()
            else:
                # No API key available; show hint
                self.notion_db_name_label.setText("(Enter Notion API key to fetch database name)")
                self.notion_db_name_label.setStyleSheet("color: #a9a9a9; font-size: 12px; margin-top: 4px;")
        else:
            self.notion_db_input.setStyleSheet("")
            self.notion_db_name_label.setText("")

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.setTabBar(EasterEggTabBar())
        tabs.tabBar().setExpanding(True)
        tabs.setStyleSheet("""
            QTabBar::tab { min-width: 200px; padding: 6px 8px; font-size: 13px; white-space: normal; }
            QTabWidget::pane { border-top: 1px solid #555; }
        """)
        
        credentials_tab = QWidget()
        cred_layout = QVBoxLayout(credentials_tab)
        
        # --- Canvas URL Section ---
        url_layout = QVBoxLayout()
        url_layout.addWidget(QLabel(T['canvas_url_label']))
        self.use_default_url_cb = QCheckBox(T['use_default_url'])
        self.use_default_url_cb.setChecked(True)
        self.use_default_url_cb.stateChanged.connect(lambda state: self._toggle_canvas_url_input(state == Qt.CheckState.Checked.value))
        url_layout.addWidget(self.use_default_url_cb)
        
        self.canvas_url_input = QLineEdit(placeholderText=T['custom_url_placeholder'])
        self.canvas_url_input.setVisible(False)
        url_layout.addWidget(self.canvas_url_input)
        cred_layout.addLayout(url_layout)
        
        # --- Canvas Key Section ---
        canvas_key_layout = QHBoxLayout()
        self.canvas_input=QLineEdit(placeholderText=T['canvas_key_placeholder'],echoMode=QLineEdit.EchoMode.Password)
        self.canvas_toggle = QPushButton()
        self.canvas_toggle.setFixedSize(30, 30)
        self.canvas_toggle.setCheckable(True)
        # Load visibility icons if available
        eye_on_path = resource_path("visibility_icon.png")
        eye_off_path = resource_path("visibility_off_icon.png")
        eye_on_icon = QIcon(eye_on_path) if os.path.exists(eye_on_path) else None
        eye_off_icon = QIcon(eye_off_path) if os.path.exists(eye_off_path) else None
        def _update_canvas_icon(checked):
            self.canvas_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
            if eye_on_icon and eye_off_icon:
                self.canvas_toggle.setIcon(eye_on_icon if checked else eye_off_icon)
                self.canvas_toggle.setIconSize(QSize(18,18))
            else:
                self.canvas_toggle.setText("Hide" if checked else "Show")
        self.canvas_toggle.clicked.connect(_update_canvas_icon)
        # initialize icon/text state
        _update_canvas_icon(False)
        canvas_key_layout.addWidget(self.canvas_input)
        canvas_key_layout.addWidget(self.canvas_toggle)
        # Load courses button
        self.load_courses_button = QPushButton("Load Courses")
        self.load_courses_button.clicked.connect(self._on_load_courses)
        self.load_courses_button.setToolTip("Fetch Canvas courses and choose which to sync")
        canvas_key_layout.addWidget(self.load_courses_button)
        
        cred_layout.addWidget(QLabel(T['canvas_key_label']))
        cred_layout.addLayout(canvas_key_layout)

        # --- Notion Key Section ---
        notion_key_layout = QHBoxLayout()
        self.notion_key_input=QLineEdit(placeholderText=T['notion_key_placeholder'],echoMode=QLineEdit.EchoMode.Password)
        self.notion_toggle = QPushButton()
        self.notion_toggle.setFixedSize(30, 30)
        self.notion_toggle.setCheckable(True)
        # Reuse icon variables if available
        def _update_notion_icon(checked):
            self.notion_key_input.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
            if eye_on_icon and eye_off_icon:
                self.notion_toggle.setIcon(eye_on_icon if checked else eye_off_icon)
                self.notion_toggle.setIconSize(QSize(18,18))
            else:
                self.notion_toggle.setText("Hide" if checked else "Show")
        self.notion_toggle.clicked.connect(_update_notion_icon)
        # initialize icon/text state
        _update_notion_icon(False)
        notion_key_layout.addWidget(self.notion_key_input)
        notion_key_layout.addWidget(self.notion_toggle)

        cred_layout.addWidget(QLabel(T['notion_key_label']))
        cred_layout.addLayout(notion_key_layout)
        
        # --- Notion DB Section ---
        cred_layout.addWidget(QLabel(T['notion_db_label']))
        self.notion_db_input=QLineEdit(placeholderText=T['notion_db_placeholder'])
        self.notion_db_input.textChanged.connect(self._on_notion_input_changed)
        cred_layout.addWidget(self.notion_db_input)
        # Label to display the resolved Notion database name (fetched asynchronously)
        self.notion_db_name_label = QLabel("")
        self.notion_db_name_label.setStyleSheet("color: #a9a9a9; font-size: 12px; margin-top: 4px;")
        cred_layout.addWidget(self.notion_db_name_label)
        # Placeholder for course list summary
        self.course_summary_label = QLabel("")
        cred_layout.addWidget(self.course_summary_label)
        
        self.help_button = QPushButton("?")
        self.help_button.setObjectName("HelpButton")
        self.help_button.setFixedSize(30, 30) 
        self.help_button.setToolTip(T['help_tooltip']) 
        self.help_button.clicked.connect(self._show_help_dialog)
        
        self.run_button=QPushButton(T['run_sync_button']) 
        self.run_button.clicked.connect(self._on_run_sync)
        self.progress_bar=QProgressBar(minimum=0,maximum=100,value=0)
        self.status_output=QTextEdit(readOnly=True)
        
        cred_layout.addSpacing(10)
        cred_layout.addWidget(self.run_button)
        cred_layout.addWidget(self.progress_bar)
        cred_layout.addWidget(self.status_output)
        cred_layout.addStretch() 
        
        help_layout = QHBoxLayout()
        help_layout.addStretch()
        help_layout.addWidget(self.help_button)
        cred_layout.addLayout(help_layout) 
        
        scheduler_tab = QWidget()
        sched_layout = QVBoxLayout(scheduler_tab)
        sched_layout.addWidget(QLabel(T['scheduler_label']))
        self.time_edit = QTimeEdit(); self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.timeChanged.connect(lambda time: self._save_settings('sync_time', time.toString("HH:mm")))
        sched_layout.addWidget(self.time_edit)
        self.startup_checkbox = QCheckBox(T['startup_checkbox'])
        self.startup_checkbox.stateChanged.connect(lambda state: set_startup(state == Qt.CheckState.Checked.value))
        sched_layout.addWidget(self.startup_checkbox)
        
        # --- Advanced toggle (hides complex options like Sync Scope) ---
        self.advanced_toggle = QCheckBox("Show Advanced Settings")
        self.advanced_toggle.setToolTip("Show advanced configuration options (for experienced users).")
        self.advanced_toggle.stateChanged.connect(lambda state: self._toggle_advanced(state == Qt.CheckState.Checked.value))
        sched_layout.addWidget(self.advanced_toggle)

        # --- Sync Scope Section (hidden by default; shown when advanced is enabled) ---
        scope_group = QGroupBox(T['sync_scope_label'])
        scope_layout = QVBoxLayout()
        # Warning shown when user unchecks all buckets (UX: nothing will sync)
        self.scope_warning_label = QLabel("Warning: If all buckets are unchecked, nothing will sync.")
        self.scope_warning_label.setStyleSheet("color: #ffd966; background-color: transparent; padding: 6px;")
        self.scope_warning_label.setWordWrap(True)
        self.scope_warning_label.setVisible(False)
        scope_layout.addWidget(self.scope_warning_label)
        self.bucket_checkboxes = {}
        buckets = [
            ('past', T['bucket_past']),
            ('undated', T['bucket_undated']),
            ('upcoming', T['bucket_upcoming']),
            ('future', T['bucket_future']),
            ('ungraded', T['bucket_ungraded'])
        ]
        # (Select All button moved below the checkboxes for better layout)

        for key, label in buckets:
            cb = QCheckBox(label)
            cb.setChecked(True) # Default checked
            cb.stateChanged.connect(self._save_bucket_settings)
            scope_layout.addWidget(cb)
            self.bucket_checkboxes[key] = cb
        # Add Select All button under the checkbox list (left-aligned)
        bottom_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setToolTip("Check all buckets")
        select_all_btn.clicked.connect(lambda: self._select_all_buckets())
        bottom_row.addWidget(select_all_btn)
        bottom_row.addStretch()
        scope_layout.addLayout(bottom_row)

        scope_group.setLayout(scope_layout)
        # default hidden; may be shown if settings say so
        scope_group.setVisible(False)
        self.scope_group = scope_group
        sched_layout.addWidget(scope_group)

        sched_layout.addStretch()
        
        tabs.addTab(credentials_tab, T['tab_credentials'])
        tabs.addTab(scheduler_tab, T['tab_scheduler'])
        # --- Time Blocks Tab (new) ---
        time_tab = QWidget()
        time_layout = QVBoxLayout(time_tab)
        time_layout.addWidget(QLabel("Time Block Generator"))

        hb = QHBoxLayout()
        hb.addWidget(QLabel("Block length (minutes):"))
        from PyQt6.QtWidgets import QSpinBox
        self.block_minutes_spin = QSpinBox()
        self.block_minutes_spin.setRange(15, 480)
        self.block_minutes_spin.setValue(90)
        hb.addWidget(self.block_minutes_spin)

        hb.addWidget(QLabel("Daily max (minutes):"))
        self.daily_max_spin = QSpinBox()
        self.daily_max_spin.setRange(0, 1440)
        self.daily_max_spin.setValue(240)
        hb.addWidget(self.daily_max_spin)

        time_layout.addLayout(hb)

        # Availability file selector (optional)
        avail_row = QHBoxLayout()
        self.avail_path_input = QLineEdit(placeholderText='Optional availability JSON path')
        avail_row.addWidget(self.avail_path_input)
        browse_btn = QPushButton('Browse')
        def _browse_avail():
            from PyQt6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getOpenFileName(self, 'Select availability JSON', os.path.expanduser('~'))
            if path:
                self.avail_path_input.setText(path)
        browse_btn.clicked.connect(_browse_avail)
        avail_row.addWidget(browse_btn)
        time_layout.addLayout(avail_row)

        # Export options
        export_row = QHBoxLayout()
        self.export_checkbox = QCheckBox('Export to Notion')
        export_row.addWidget(self.export_checkbox)
        export_row.addWidget(QLabel('Database ID:'))
        self.export_db_input = QLineEdit()
        export_row.addWidget(self.export_db_input)
        # No confirmation checkbox — keep a single Export control for simplicity
        time_layout.addLayout(export_row)

        # Buttons
        btn_row = QHBoxLayout()
        self.generate_blocks_btn = QPushButton('Generate Blocks (Dry Run)')
        self.generate_blocks_btn.clicked.connect(self._on_generate_blocks)
        btn_row.addWidget(self.generate_blocks_btn)
        self.export_confirm_btn = QPushButton('Generate & Export')
        self.export_confirm_btn.clicked.connect(lambda: self._on_generate_blocks(export=True))
        # Export button disabled until user opts-in and db id provided
        self.export_confirm_btn.setEnabled(False)
        btn_row.addWidget(self.export_confirm_btn)
        time_layout.addLayout(btn_row)

        # Output preview
        self.blocks_preview = QTextEdit(readOnly=True)
        time_layout.addWidget(self.blocks_preview)

        tabs.addTab(time_tab, 'Time Blocks')
        main_layout.addWidget(tabs)

    def _toggle_canvas_url_input(self, checked):
        self.canvas_url_input.setVisible(not checked)
        self._save_settings("use_default_url", checked)

    def _toggle_advanced(self, checked: bool):
        # Show or hide advanced settings (sync scope)
        try:
            self.scope_group.setVisible(checked)
        except Exception:
            pass
        # Persist the value
        self._save_settings("show_advanced", bool(checked))

    def _update_course_summary(self):
        selected = self._load_settings_value("selected_course_ids", [])
        if selected:
            self.course_summary_label.setText(f"Selected courses: {len(selected)}")
        else:
            self.course_summary_label.setText("")

    def _save_bucket_settings(self):
        # Save selected buckets. UX note: If the user unchecks all buckets we
        # show a warning and persist an empty selection. This avoids surprising
        # behavior from auto-selecting all buckets and makes the effect explicit.
        buckets = [k for k, cb in self.bucket_checkboxes.items() if cb.isChecked()]
        if not buckets:
            try:
                self.scope_warning_label.setVisible(True)
            except Exception:
                pass
            try:
                if hasattr(self, 'status_output'):
                    self.status_output.append("Warning: No sync buckets selected — nothing will be synced.")
            except Exception:
                pass
        else:
            try:
                self.scope_warning_label.setVisible(False)
            except Exception:
                pass

        self._save_settings("buckets", buckets)

    def _select_all_buckets(self):
        for k, cb in self.bucket_checkboxes.items():
            try:
                cb.setChecked(True)
            except Exception:
                pass
        try:
            self.scope_warning_label.setVisible(False)
        except Exception:
            pass
        self._save_bucket_settings()

    def _on_run_sync(self):
        # Save keys to keyring
        self._save_settings("canvas_key", self.canvas_input.text().strip())
        self._save_settings("notion_key", self.notion_key_input.text().strip())
        
        # Save DB ID
        notion_db_input_text = self.notion_db_input.text().strip()
        match = re.search(r"notion\.so/(?:[^/]+/)?([a-f0-9]{32})", notion_db_input_text)
        if match:
            notion_db_id = match.group(1)
            self.notion_db_input.textChanged.disconnect(self._on_notion_input_changed)
            self.notion_db_input.setText(notion_db_id)
            self.notion_db_input.textChanged.connect(self._on_notion_input_changed)
        else:
            notion_db_id = notion_db_input_text
        self._save_settings("notion_db_id", notion_db_id)
        
        # Get URL
        if self.use_default_url_cb.isChecked():
            base_url = "https://keyinstitute.instructure.com/api/v1"
        else:
            base_url = self.canvas_url_input.text().strip()
            self._save_settings("canvas_url", base_url)
        
        # Get Buckets
        buckets = [k for k, cb in self.bucket_checkboxes.items() if cb.isChecked()]
        
        canvas_key=self.canvas_input.text().strip()
        notion_key=self.notion_key_input.text().strip()
        
        if not all([canvas_key,notion_key,notion_db_id]):
            self.status_output.append(T['sync_error_all_fields'])
            return
            
        self.run_button.setEnabled(False)
        self.status_output.clear()
        self.progress_bar.setValue(0)
        
        # --- MODIFIED: Disable tray actions for crash fix ---
        if hasattr(self, 'tray_run_action'):
            self.tray_run_action.setEnabled(False)
        if hasattr(self, 'tray_quit_action'):
            self.tray_quit_action.setEnabled(False)
        # --- END OF MODIFICATION ---
        
        # --- MODIFIED: Load flag and pass to thread ---
        first_sync_complete = self._load_settings_value("first_sync_complete", False)
        # Load selected course ids
        selected_course_ids = self._load_settings_value("selected_course_ids", [])

        self.sync_thread=SyncThread(canvas_key,notion_key,notion_db_id, first_sync_complete, base_url, buckets, selected_course_ids)
        
        self.sync_thread.update_status.connect(self.status_output.append)
        self.sync_thread.update_progress.connect(self.progress_bar.setValue)
        
        # --- MODIFIED: Connect to new finished slot for crash fix ---
        self.sync_thread.finished.connect(self._on_sync_finished)
        
        # --- NEW: Connect success signal to mark flag ---
        self.sync_thread.sync_succeeded.connect(self._on_sync_success)
        self.sync_thread.sync_failed.connect(self._on_sync_fail)
        
        self.sync_thread.start()

    def _on_generate_blocks(self, export=False):
        # Disable buttons while running
        self.generate_blocks_btn.setEnabled(False)
        self.export_confirm_btn.setEnabled(False)

        canvas_key = self.canvas_input.text().strip() or keyring.get_password(APP_NAME, 'canvas_key')
        if self.use_default_url_cb.isChecked():
            base_url = 'https://keyinstitute.instructure.com/api/v1'
        else:
            base_url = self.canvas_url_input.text().strip()

        buckets = [k for k, cb in self.bucket_checkboxes.items() if cb.isChecked()]
        selected_course_ids = self._load_settings_value('selected_course_ids', [])

        block_minutes = int(self.block_minutes_spin.value())
        daily_max = int(self.daily_max_spin.value()) if self.daily_max_spin.value() > 0 else None

        availability = None
        avail_path = self.avail_path_input.text().strip()
        if avail_path and os.path.exists(avail_path):
            try:
                with open(avail_path, 'r') as f: availability = json.load(f)
            except Exception as e:
                self.status_output.append(f'Could not read availability file: {e}')

        notion_key = self.notion_key_input.text().strip() or keyring.get_password(APP_NAME, 'notion_key')
        notion_db_id = self.export_db_input.text().strip()

        # If this invocation requested export, ensure the user explicitly checked
        # the export checkbox and provided a database id.
        if export:
            if not self.export_checkbox.isChecked():
                self.status_output.append('Export not enabled. Please check "Export to Notion".')
                # Re-enable UI
                self.generate_blocks_btn.setEnabled(True)
                self.export_confirm_btn.setEnabled(True)
                return
            if not notion_db_id:
                self.status_output.append('No Notion database id provided. Enter a database id to export.')
                self.generate_blocks_btn.setEnabled(True)
                self.export_confirm_btn.setEnabled(True)
                return

        # Start background worker
        self.timeblock_thread = TimeBlockThread(canvas_key, base_url, buckets, selected_course_ids, block_minutes, daily_max, availability, notion_key, notion_db_id, export)
        self.timeblock_thread.finished.connect(self._on_timeblock_finished)
        self.timeblock_thread.start()

        # Maintain export button enabled state based on user controls
        try:
            self.export_checkbox.stateChanged.connect(lambda _: self._update_export_controls())
            self.export_db_input.textChanged.connect(lambda _: self._update_export_controls())
        except Exception:
            pass
        # Ensure initial state is correct
        try:
            self._update_export_controls()
        except Exception:
            pass

    def _update_export_controls(self):
        """Enable the Generate & Export button only when the user opted in and provided a DB id."""
        try:
            enabled = False
            if getattr(self, 'export_checkbox', None):
                enabled = self.export_checkbox.isChecked() and bool(self.export_db_input.text().strip())
            self.export_confirm_btn.setEnabled(enabled)
        except Exception:
            pass

    def _on_timeblock_finished(self, blocks, message):
        # Re-enable buttons
        try:
            self.generate_blocks_btn.setEnabled(True)
            self.export_confirm_btn.setEnabled(True)
        except Exception:
            pass

        if blocks is None:
            self.blocks_preview.setPlainText(message)
            self.status_output.append(message)
            return

        # Show summary and first few blocks
        preview = [f"{len(blocks)} blocks planned. {message}\n"]
        for b in blocks[:10]:
            preview.append(json.dumps(b, indent=2))
        self.blocks_preview.setPlainText('\n\n'.join(preview))
        self.status_output.append(message)

# --- Platform-specific and background functions (Unchanged) ---
def get_startup_script_path(): return f'"{sys.executable}" --daemon'
def set_startup(enable: bool):
    if sys.platform == "win32":
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enable: winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_startup_script_path())
                else: winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            if enable:
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, get_startup_script_path())
        except Exception: pass
    elif sys.platform == "darwin":
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/com.{APP_NAME.lower()}.plist")
        if enable:
            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>Label</key><string>com.{APP_NAME.lower()}</string><key>ProgramArguments</key><array><string>{sys.executable}</string><string>--daemon</string></array><key>RunAtLoad</key><true/></dict></plist>"""
            with open(plist_path, "w") as f: f.write(plist_content)
        else:
            if os.path.exists(plist_path): os.remove(plist_path)
def is_startup_enabled():
    if sys.platform == "win32":
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, APP_NAME)
            return True
        except FileNotFoundError: return False
    elif sys.platform == "darwin":
        plist_path = os.path.expanduser(f"~/Library/LaunchAgents/com.{APP_NAME.lower()}.plist")
        return os.path.exists(plist_path)
    return False

# --- log_message is now using the safe global path ---
def log_message(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); log_entry = f"[{timestamp}] {message}"; print(log_entry)
    with open(log_file_path_global, 'a', encoding='utf-8') as f: f.write(log_entry + '\n')

# --- MODIFIED: Background sync (Using safe path constants) ---
def _show_notification(title, message, icon_type):
    app = QApplication.instance()
    if app:
        # We need to keep a reference to the tray icon, otherwise it might be garbage collected
        # or not show up properly if created temporarily.
        # However, for a simple notification, creating a new one usually works if the app loop is running.
        tray = QSystemTrayIcon(QIcon(resource_path("icon.png")), app)
        tray.show()
        tray.showMessage(title, message, icon_type, 3000)

def run_background_sync():
    log_message("--- Triggering Scheduled Sync ---")
    # --- FIX: Use safe path constant ---
    if not os.path.exists(credentials_file_path): 
        log_message("ERROR: credentials.json not found."); return

    creds = {}
    try:
        # --- FIX: Use safe path constant ---
        with open(credentials_file_path, 'r') as f: creds = json.load(f)
    except (KeyError, json.JSONDecodeError): 
        log_message("ERROR: credentials.json is missing keys or is corrupt.")
        return

    try:
        # Load keys from keyring
        canvas_key = keyring.get_password(APP_NAME, "canvas_key")
        notion_key = keyring.get_password(APP_NAME, "notion_key")
        
        if not canvas_key or not notion_key:
             # Fallback to json if not in keyring (migration edge case)
             canvas_key = creds.get('canvas_key')
             notion_key = creds.get('notion_key')
        
        if not canvas_key or not notion_key:
            log_message("ERROR: API keys not found.")
            return

        notion_db_id = creds['notion_db_id']
        # --- NEW: Load the flag ---
        first_sync_complete = creds.get('first_sync_complete', False)
        
        # Load new settings
        base_url = creds.get("canvas_url", "https://keyinstitute.instructure.com/api/v1")
        if creds.get("use_default_url", True):
            base_url = "https://keyinstitute.instructure.com/api/v1"
            
        buckets = creds.get("buckets", ["past", "undated", "upcoming", "future", "ungraded"])
        
        log_message("Verifying Notion database properties...")
        schema_ok, date_property_name = ensure_database_properties(notion_key, notion_db_id, log_message)
        if not schema_ok:
            log_message("❌ Database setup failed. Aborting scheduled sync.")
            _show_notification(T['notification_fail_title'], T['notification_fail_msg'], QSystemTrayIcon.MessageIcon.Warning)
            return # Stop the sync
        log_message(f"   Using date property: '{date_property_name}'")
        
        selected_course_ids = creds.get('selected_course_ids', [])
        assignments = get_canvas_assignments(canvas_key, base_url, buckets, selected_course_ids, log_message)
        
        # --- MODIFIED: Pass is_first_sync flag ---
        add_to_notion(
            notion_key, 
            notion_db_id, 
            assignments, 
            log_message, 
            date_property_name,
            is_first_sync=not first_sync_complete
        )
        
        log_message("--- Scheduled Sync Finished ---")
        _show_notification(T['notification_success_title'], T['notification_success_msg'], QSystemTrayIcon.MessageIcon.Information)

        # --- NEW: Save the flag if this was the first sync ---
        if not first_sync_complete:
            log_message("Marking first sync as complete.")
            creds["first_sync_complete"] = True
            # --- FIX: Use safe path constant ---
            with open(credentials_file_path, 'w') as f: 
                json.dump(creds, f, indent=4)

    except Exception as e: 
        log_message(f"An error occurred during scheduled sync: {e}")
        _show_notification(T['notification_fail_title'], f"{T['notification_fail_msg']} {e}", QSystemTrayIcon.MessageIcon.Warning)

def start_scheduler_daemon():
    # Create QApplication to support QSystemTrayIcon
    app = QApplication(sys.argv)
    
    sync_time = "23:59"
    # --- FIX: Use safe path constant ---
    if os.path.exists(credentials_file_path):
        try:
            # --- FIX: Use safe path constant ---
            with open(credentials_file_path, 'r') as f: creds = json.load(f); sync_time = creds.get('sync_time', '23:59')
        except (json.JSONDecodeError, IOError): pass
    log_message(f"Scheduler daemon started. Sync scheduled for {sync_time} daily.")
    schedule.every().day.at(sync_time).do(run_background_sync)
    
    # Use QTimer to run schedule.run_pending() periodically
    timer = QTimer()
    timer.timeout.connect(schedule.run_pending)
    timer.start(60000) # Check every minute
    
    sys.exit(app.exec())

# --- Main execution block (MODIFIED for safe path and resources) ---
if __name__ == "__main__":
    if '--daemon' in sys.argv: start_scheduler_daemon(); sys.exit()
    elif '--background' in sys.argv: run_background_sync(); sys.exit()
    
    app = QApplication(sys.argv)
    
    # --- FIX: Use resource_path for font file ---
    font_path = resource_path("Figtree-VariableFont_wght.ttf")
    if os.path.exists(font_path): 
        QFontDatabase.addApplicationFont(font_path)
    else: 
        print("WARNING: Figtree-VariableFont_wght.ttf not found.")
    
    app.setStyleSheet(MODERN_QSS)
    app.setQuitOnLastWindowClosed(False)

    window = NotionSyncApp()
    
    # --- FIX: Use resource_path for icon file ---
    icon_path = resource_path("icon.png")
    if not os.path.exists(icon_path): 
        print("ERROR: icon.png not found!"); sys.exit(1)
    
    tray_icon = QSystemTrayIcon(QIcon(icon_path), parent=app)
    tray_icon.setToolTip(T['tray_tooltip'])
    menu = QMenu()
    
    run_sync_action = QAction(T['tray_run_sync'], app)
    run_sync_action.triggered.connect(window._on_run_sync)
    menu.addAction(run_sync_action)
    menu.addSeparator()
    
    show_action = QAction(T['tray_show_window'], app)
    show_action.triggered.connect(window.show)
    menu.addAction(show_action)
    menu.addSeparator()
    
    quit_action = QAction(T['tray_quit'], app)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)
    
    # --- MODIFIED: Pass tray actions to window for crash fix ---
    window.set_tray_actions(run_sync_action, quit_action)
    
    tray_icon.setContextMenu(menu)
    tray_icon.show()
    
    # --- FIX: Use safe path constant ---
    if not os.path.exists(credentials_file_path): window.show()
    
    sys.exit(app.exec())