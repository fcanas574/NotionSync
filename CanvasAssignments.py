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
    QComboBox, QGroupBox, QStackedWidget, QButtonGroup, QSizePolicy # --- NEW: Added QComboBox, QStackedWidget, QButtonGroup and QSizePolicy ---
)
from PyQt6.QtGui import QIcon, QAction, QFontDatabase, QFont, QPixmap, QPainter, QColor, QPolygonF
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTime, QPointF, QSize, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QObject, pyqtProperty
from PyQt6.QtWidgets import QGraphicsOpacityEffect

from canvas_notion_calendar_db_v1 import (
    get_canvas_assignments,
    add_to_notion,
    ensure_database_properties,
    get_canvas_courses,
    get_notion_database_name,
    add_schedule_blocks_to_database,
)

# --- PATHING & RESOURCE HELPERS (NEW) ---
APP_NAME = "NotionSync"

def resource_path(relative_path):
    """Return absolute path to a resource file.

    Works in two modes:
    - Development: resolves relative to this file's directory.
    - Bundled (PyInstaller): resolves via the `_MEIPASS` temporary folder.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))

    # Try requested path first, then fall back into an `assets/` subfolder
    candidate = os.path.join(base_path, relative_path)
    if os.path.exists(candidate):
        return candidate
    alt = os.path.join(base_path, 'assets', relative_path)
    if os.path.exists(alt):
        return alt
    return candidate

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
log_file_path_global = SAFE_PATHS['log']

# Debug trace removed


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

# --- QSS Stylesheet (Improved for modern look) ---
MODERN_QSS = """
QWidget {
    background-color: #22252a; color: #e8eef6;
    font-family: 'Figtree', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 13px;
}
QTabWidget::pane { border: 1px solid #32363b; border-top: none; }
QTabBar::tab {
    background: transparent; border: 1px solid transparent; border-bottom: none;
    padding: 8px 14px; border-top-left-radius: 6px; border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #2b2b2f; border: 1px solid #3a3f44; }
QTabBar::tab:!selected { margin-top: 2px; }
QLabel { background-color: transparent; }
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #27292d; border: 1px solid #3a3f44; border-radius: 8px; padding: 6px;
}
QLineEdit:focus, QTextEdit:focus { border: 1px solid #0a84ff; }

/* Modern, rounded buttons */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0a84ff, stop:1 #0666d6);
    color: white; font-weight: 600; border: none; border-radius: 8px; padding: 8px 14px;
}
QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0c8bff, stop:1 #0570d7); }
QPushButton:pressed { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #0666d6, stop:1 #0459b8); }
QPushButton:disabled { background-color: #3a3f44; color: #9ea7b3; }

QPushButton#HelpButton {
    background-color: transparent; color: #cfe8ff; font-weight: 700; font-size: 15px;
    border-radius: 50px; padding: 6px 10px; border: 1px solid rgba(255,255,255,0.05);
}
QPushButton#HelpButton:hover { background-color: rgba(255,255,255,0.02); }

QTextEdit { background-color: #1f2225; border: 1px solid #303438; border-radius: 8px; padding: 8px; }
QProgressBar { border: 1px solid #303438; border-radius: 8px; text-align: center; color: #e8eef6; }
QProgressBar::chunk { background-color: #0a84ff; border-radius: 6px; margin: 1px; }
QMenu { background-color: #2a2d31; border: 1px solid #373b40; }
QMenu::item { padding: 8px 18px; }
QMenu::item:selected { background-color: rgba(10,132,255,0.12); }
QMenu::separator { height: 1px; background: #36393f; margin: 4px 0px; }
QTimeEdit { background-color: #27292d; border: 1px solid #3a3f44; border-radius: 6px; padding: 4px; }
QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #3a3f44; border-radius: 4px; }
QCheckBox::indicator:unchecked { background-color: #27292d; }
QCheckBox::indicator:checked { background-color: transparent; border: 1px solid #0a84ff; image: url(icon:checkmark.png); }
QHeaderView::section { background-color: #2b2e31; padding: 6px; border: 1px solid #35383d; }
QTreeView, QListView, QTableView { background-color: #1f2225; alternate-background-color: #26282b; gridline-color: #2f3336; }

/* Ensure small controls look modern */
QSpinBox, QComboBox { background-color: #27292d; border: 1px solid #3a3f44; border-radius: 6px; padding: 4px; }

/* Use subtle focus indicator for keyboard navigation (Qt doesn't support box-shadow) */
*:focus { outline: none; }
/* Use a thin colored border for focus states instead of box-shadow */
QLineEdit:focus, QTextEdit:focus { border: 1px solid #0a84ff; }
QPushButton:focus { border: 1px solid rgba(10,132,255,0.25); }

QTextEdit#HelpText { background-color: transparent; border: none; padding: 10px; }
# End of MODERN_QSS
"""

# If a bundled `check.png` exists, update the QSS to reference its absolute path
_check_img_path = resource_path("check.png")
_check_img_path = _check_img_path.replace("\\", "/")
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


class SettingsDialog(QDialog):
    """Settings dialog now contains Sync Scope (buckets) and an advanced
    toggle-list instead of the sync blocks button. Values are exposed as
    attributes after the dialog is accepted.
    """
    def __init__(self, parent=None, startup_checked=False, advanced_checked=False, current_buckets=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.resize(520, 420)

        self.selected_buckets = current_buckets or []

        layout = QVBoxLayout(self)

        # Startup toggle
        self.startup_cb = QCheckBox(T['startup_checkbox'])
        self.startup_cb.setChecked(startup_checked)
        layout.addWidget(self.startup_cb)

        # Sync Scope (Buckets) - move here from Scheduler
        scope_group = QGroupBox(T['sync_scope_label'])
        scope_layout = QVBoxLayout()

        self.bucket_checkboxes = {}
        buckets = [
            ('past', T['bucket_past']),
            ('undated', T['bucket_undated']),
            ('upcoming', T['bucket_upcoming']),
            ('future', T['bucket_future']),
            ('ungraded', T['bucket_ungraded'])
        ]

        for key, label in buckets:
            cb = QCheckBox(label)
            cb.setChecked(key in (self.selected_buckets or [k for k, _ in buckets]))
            self.bucket_checkboxes[key] = cb
            scope_layout.addWidget(cb)

        # Select all for convenience
        select_all_row = QHBoxLayout()
        select_all_btn = QPushButton('Select All')
        select_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb in self.bucket_checkboxes.values()])
        select_all_row.addWidget(select_all_btn)
        select_all_row.addStretch()
        scope_layout.addLayout(select_all_row)

        scope_group.setLayout(scope_layout)
        layout.addWidget(scope_group)

        # Advanced features as a toggle list (replace single advanced checkbox)
        adv_group = QGroupBox('Advanced Features')
        adv_layout = QVBoxLayout()
        # For now we expose the existing 'show_advanced' flag as a toggle inside
        # the list; future advanced toggles may be added here.
        self.adv_show_advanced = QCheckBox('Show Advanced Settings')
        self.adv_show_advanced.setChecked(advanced_checked)
        adv_layout.addWidget(self.adv_show_advanced)
        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)

        # Footer buttons
        foot = QHBoxLayout()
        foot.addStretch()
        apply_btn = QPushButton('Apply')
        close_btn = QPushButton(T['help_close'])
        foot.addWidget(apply_btn)
        foot.addWidget(close_btn)
        layout.addLayout(foot)

        close_btn.clicked.connect(self.reject)
        apply_btn.clicked.connect(self._on_apply)

    def _on_apply(self):
        # Collect selected buckets and advanced flags
        try:
            self.selected_buckets = [k for k, cb in self.bucket_checkboxes.items() if cb.isChecked()]
        except Exception:
            self.selected_buckets = []
        try:
            self.startup_selected = self.startup_cb.isChecked()
        except Exception:
            self.startup_selected = False
        try:
            self.advanced_flags = {'show_advanced': bool(self.adv_show_advanced.isChecked())}
        except Exception:
            self.advanced_flags = {'show_advanced': False}
        self.accept()


class LabelOpacityHelper(QObject):
    """Helper QObject exposing a Qt property `opacity` so we can animate
    a button's text opacity without affecting the icon.
    """
    def __init__(self, button):
        super().__init__()
        self._button = button
        self._opacity = 1.0

    @pyqtProperty(float)
    def opacity(self):
        return float(self._opacity)

    @opacity.setter
    def opacity(self, value):
        try:
            v = max(0.0, min(1.0, float(value)))
        except Exception:
            v = 1.0
        self._opacity = v
        alpha = int(v * 255)
        # Use the same text color as the QSS base but with varying alpha.
        # Keep padding so layout sizeHint stays consistent.
        try:
            # Preserve custom font-size for nav buttons so it doesn't reset after fade animations.
            self._button.setStyleSheet(f"text-align: left; padding-left: 8px; font-size: 11px; color: rgba(232,238,246,{alpha});")
        except Exception:
            pass


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
        main_layout = QHBoxLayout(self)
        # We'll use a QStackedWidget for content pages and navigation buttons
        self.page_stack = QStackedWidget()
        
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

        # Scheduler tab layout (kept minimal) — sync buckets moved into Settings dialog
        # Keep an attribute for bucket_checkboxes state so other code can read/write
        self.bucket_checkboxes = {}
        # Leave any detailed UI for the settings dialog
        sched_layout.addStretch()
        
        # Add pages to stacked widget instead of tabs
        self.page_stack.addWidget(credentials_tab)  # index 0
        self.page_stack.addWidget(scheduler_tab)    # index 1
        # --- Time Blocks Page (new) ---
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

        self.page_stack.addWidget(time_tab)         # index 2

        # Build a sidebar to hold navigation buttons and a bottom settings area
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(8, 8, 8, 8)
        sidebar_layout.setSpacing(8)

        # Navigation buttons (Assignment Sync, Scheduler, Timeblocker)
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(6)
        # store placeholder for nav opacity (not used for full fade to preserve icons)
        self._nav_opacity = None

        # Collapse/expand button at top (stay pinned)
        collapse_row = QHBoxLayout()
        collapse_row.setContentsMargins(0, 0, 0, 0)
        collapse_row.setSpacing(0)
        collapse_btn = QPushButton()
        collapse_btn.setFixedSize(36, 36)
        collapse_btn.setSizePolicy(collapse_btn.sizePolicy().horizontalPolicy(), collapse_btn.sizePolicy().verticalPolicy())
        # Try to load provided icon
        view_icon_path = resource_path("view_sidebar.png")
        if os.path.exists(view_icon_path):
            try:
                collapse_btn.setIcon(QIcon(view_icon_path))
                collapse_btn.setIconSize(QSize(20, 20))
            except Exception:
                collapse_btn.setText('☰')
        else:
            collapse_btn.setText('☰')
        collapse_btn.setToolTip('Toggle sidebar')
        collapse_row.addWidget(collapse_btn)
        collapse_row.addStretch()
        # Put the collapse controls inside a dedicated top_bar widget so it stays pinned
        top_bar = QWidget()
        top_bar.setLayout(collapse_row)

        # Build a top container that holds the collapse icon and the navigation
        top_container = QWidget()
        top_container_layout = QVBoxLayout(top_container)
        top_container_layout.setContentsMargins(0, 0, 0, 0)
        top_container_layout.setSpacing(6)
        top_container_layout.addWidget(top_bar)

        self.nav_buttons = []
        btn_assign = QPushButton('Assignment Sync')
        btn_sched = QPushButton('Scheduler')
        btn_time = QPushButton('Timeblocker')

        # Load icons for nav buttons if available
        try:
            sync_icon_path = resource_path('sync.png')
            if os.path.exists(sync_icon_path):
                btn_assign.setIcon(QIcon(sync_icon_path))
                btn_assign.setIconSize(QSize(18, 18))
            sched_icon_path = resource_path('schedule.png')
            if os.path.exists(sched_icon_path):
                btn_sched.setIcon(QIcon(sched_icon_path))
                btn_sched.setIconSize(QSize(18, 18))
            time_icon_path = resource_path('book_ribbon.png')
            if os.path.exists(time_icon_path):
                btn_time.setIcon(QIcon(time_icon_path))
                btn_time.setIconSize(QSize(18, 18))
        except Exception:
            pass

        for b in (btn_assign, btn_sched, btn_time):
            b.setCheckable(True)
            b.setMinimumHeight(36)
            # Reduce font size and explicitly set consistent light text color.
            b.setStyleSheet('text-align: left; padding-left: 8px; font-size: 11px; color: rgba(232,238,246,255);')
            nav_layout.addWidget(b)
            self.nav_buttons.append(b)

        # Make the first selected
        btn_assign.setChecked(True)

        # Wrap navigation container in a fixed-width wrapper so we can animate
        # its width without affecting the rest of the layout.
        nav_wrapper = QWidget()
        nav_wrapper_layout = QVBoxLayout(nav_wrapper)
        nav_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        nav_wrapper_layout.setSpacing(0)
        # initial min/max for the nav area so we can animate `maximumWidth`
        # allow the wrapper to shrink to an icon-only width and expand to full width
        nav_wrapper.setMinimumWidth(72)
        nav_wrapper.setMaximumWidth(280)
        nav_wrapper_layout.addWidget(nav_container)
        top_container_layout.addWidget(nav_wrapper)
        sidebar_layout.addWidget(top_container, alignment=Qt.AlignmentFlag.AlignTop)
        # Expose for instrumentation / external diagnostics
        self._nav_wrapper = nav_wrapper
        self._sidebar_widget = sidebar
        self._collapse_btn = collapse_btn

        # Add an opacity effect to the whole sidebar so we can fade it during
        # collapse/expand without producing layout jitter while resizing.
        try:
            sidebar_effect = QGraphicsOpacityEffect(sidebar)
            sidebar.setGraphicsEffect(sidebar_effect)
            sidebar_effect.setOpacity(1.0)
            self._sidebar_opacity_effect = sidebar_effect
        except Exception:
            self._sidebar_opacity_effect = None

        # Sidebar collapsed state
        self._sidebar_collapsed = False

        # Prepare LabelOpacityHelper instances for each nav button (created lazily)
        for b in self.nav_buttons:
            try:
                if not hasattr(b, '_fader'):
                    b._fader = LabelOpacityHelper(b)
            except Exception:
                pass

        def _toggle_sidebar():
            # Simplified toggle animation: remove window locking & pauses to avoid visual bounce.
            from PyQt6.QtCore import QSequentialAnimationGroup, QParallelAnimationGroup, QAbstractAnimation

            # Prevent re-entry while an animation is running.
            try:
                if getattr(self, '_sidebar_anim', None) and self._sidebar_anim.state() == QAbstractAnimation.State.Running:
                    return
            except Exception:
                pass

            current_collapsed = self._sidebar_collapsed
            collapsed_width = 72

            if not current_collapsed:
                # Remember current width for expansion restore.
                try:
                    self._last_expanded_width = nav_wrapper.width()
                except Exception:
                    self._last_expanded_width = 280

            expanded_width = getattr(self, '_last_expanded_width', 280)
            if expanded_width < 200:
                expanded_width = 280

            seq_group = QSequentialAnimationGroup()

            if not current_collapsed:
                # COLLAPSING: fade labels then shrink width.
                fade_group = QParallelAnimationGroup()
                for nb in self.nav_buttons:
                    try:
                        if not hasattr(nb, '_fader'):
                            nb._fader = LabelOpacityHelper(nb)
                        anim = QPropertyAnimation(nb._fader, b"opacity")
                        anim.setDuration(150)
                        anim.setStartValue(1.0)
                        anim.setEndValue(0.0)
                        fade_group.addAnimation(anim)
                    except Exception:
                        pass
                try:
                    sb = getattr(sidebar, '_settings_btn', None)
                    if sb:
                        if not hasattr(sb, '_fader'):
                            sb._fader = LabelOpacityHelper(sb)
                        s_anim = QPropertyAnimation(sb._fader, b"opacity")
                        s_anim.setDuration(150)
                        s_anim.setStartValue(1.0)
                        s_anim.setEndValue(0.0)
                        fade_group.addAnimation(s_anim)
                except Exception:
                    pass
                seq_group.addAnimation(fade_group)

                width_anim = QPropertyAnimation(nav_wrapper, b"maximumWidth")
                width_anim.setDuration(260)
                width_anim.setStartValue(expanded_width)
                width_anim.setEndValue(collapsed_width)
                width_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                seq_group.addAnimation(width_anim)

                def _on_collapse_finished():
                    self._sidebar_collapsed = True
                    style_centered = 'text-align: center; padding: 0px; border: none; font-size: 11px; color: rgba(232,238,246,255);'
                    for nb in self.nav_buttons:
                        try:
                            if not hasattr(nb, '_full_text'):
                                nb._full_text = nb.text()
                            nb.setText('')
                            nb.setStyleSheet(style_centered)
                            nb.setToolTip(getattr(nb, '_full_text', ''))
                            nb.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                            nb.setFixedSize(QSize(72, 64))
                            nb.setIconSize(QSize(24, 24))
                        except Exception:
                            pass
                    try:
                        sb = getattr(sidebar, '_settings_btn', None)
                        if sb:
                            if not hasattr(sb, '_full_text'):
                                sb._full_text = sb.text()
                            sb.setText('')
                            sb.setStyleSheet(style_centered)
                            sb.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                            sb.setFixedSize(QSize(72, 64))
                            sb.setIconSize(QSize(24, 24))
                    except Exception:
                        pass
                seq_group.finished.connect(_on_collapse_finished)
            else:
                # EXPANDING: prepare labels (transparent) then expand width then fade in.
                def _prepare():
                    style_transparent = 'text-align: left; padding-left: 8px; font-size: 11px; color: rgba(232,238,246,0); border: none;'
                    for nb in self.nav_buttons:
                        try:
                            full = getattr(nb, '_full_text', nb.text())
                            nb.setText(full)
                            nb.setStyleSheet(style_transparent)
                            nb.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
                            nb.setMinimumWidth(0)
                            nb.setMaximumWidth(16777215)
                            nb.setIconSize(QSize(18, 18))
                            if not hasattr(nb, '_fader'):
                                nb._fader = LabelOpacityHelper(nb)
                            nb._fader._opacity = 0.0
                        except Exception:
                            pass
                    try:
                        sb = getattr(sidebar, '_settings_btn', None)
                        if sb:
                            full = getattr(sb, '_full_text', sb.text())
                            sb.setText(full)
                            sb.setStyleSheet(style_transparent)
                            sb.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
                            sb.setMinimumWidth(0)
                            sb.setMaximumWidth(16777215)
                            sb.setIconSize(QSize(18, 18))
                            if not hasattr(sb, '_fader'):
                                sb._fader = LabelOpacityHelper(sb)
                            sb._fader._opacity = 0.0
                    except Exception:
                        pass
                    try:
                        nav_wrapper.setMaximumWidth(collapsed_width)
                    except Exception:
                        pass
                _prepare()

                width_anim = QPropertyAnimation(nav_wrapper, b"maximumWidth")
                width_anim.setDuration(300)
                width_anim.setStartValue(collapsed_width)
                width_anim.setEndValue(expanded_width)
                width_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
                seq_group.addAnimation(width_anim)

                fade_group = QParallelAnimationGroup()
                for nb in self.nav_buttons:
                    try:
                        anim = QPropertyAnimation(nb._fader, b"opacity")
                        anim.setDuration(160)
                        anim.setStartValue(0.0)
                        anim.setEndValue(1.0)
                        fade_group.addAnimation(anim)
                    except Exception:
                        pass
                try:
                    sb = getattr(sidebar, '_settings_btn', None)
                    if sb and hasattr(sb, '_fader'):
                        s_anim = QPropertyAnimation(sb._fader, b"opacity")
                        s_anim.setDuration(160)
                        s_anim.setStartValue(0.0)
                        s_anim.setEndValue(1.0)
                        fade_group.addAnimation(s_anim)
                except Exception:
                    pass
                seq_group.addAnimation(fade_group)

                def _on_expand_finished():
                    self._sidebar_collapsed = False
                    try:
                        nav_wrapper.setMaximumWidth(expanded_width)
                    except Exception:
                        pass
                seq_group.finished.connect(_on_expand_finished)

            self._sidebar_anim = seq_group
            try:
                seq_group.start()
            except Exception:
                pass

        collapse_btn.clicked.connect(_toggle_sidebar)

        # Wire navigation to page stack
        def _switch_to(index):
            try:
                # uncheck all then check the selected one
                for i, nb in enumerate(self.nav_buttons):
                    nb.setChecked(i == index)
                self.page_stack.setCurrentIndex(index)
            except Exception:
                pass

        btn_assign.clicked.connect(lambda: _switch_to(0))
        btn_sched.clicked.connect(lambda: _switch_to(1))
        btn_time.clicked.connect(lambda: _switch_to(2))

        # Create hidden startup and advanced toggles as attributes (UI moved to Settings dialog)
        # Keep them as objects so existing code that reads/writes their state continues to work.
        self.startup_checkbox = QCheckBox(T['startup_checkbox'])
        self.startup_checkbox.setVisible(False)
        self.startup_checkbox.stateChanged.connect(lambda state: set_startup(state == Qt.CheckState.Checked.value))

        self.advanced_toggle = QCheckBox("Show Advanced Settings")
        self.advanced_toggle.setVisible(False)
        self.advanced_toggle.setToolTip("Show advanced configuration options (for experienced users).")
        self.advanced_toggle.stateChanged.connect(lambda state: self._toggle_advanced(state == Qt.CheckState.Checked.value))

        # Provide a Settings button under the nav so settings are accessible but
        # not pinned to the bottom-left of the app anymore.
        # push the settings button to the bottom (not in the top-aligned group)
        sidebar_layout.addStretch()
        settings_btn = QPushButton('Settings')
        settings_btn.clicked.connect(lambda: self._open_settings_dialog())
        # Load settings icon
        try:
            settings_icon_path = resource_path('settings.png')
            if os.path.exists(settings_icon_path):
                settings_btn.setIcon(QIcon(settings_icon_path))
                settings_btn.setIconSize(QSize(18, 18))
        except Exception:
            pass
        try:
            # Match nav button font size and color for consistency.
            settings_btn.setStyleSheet('text-align: left; padding-left: 8px; font-size: 11px; color: rgba(232,238,246,255);')
        except Exception:
            pass
        # Add opacity so settings fades with nav
        try:
            settings_effect = QGraphicsOpacityEffect(settings_btn)
            settings_btn.setGraphicsEffect(settings_effect)
            settings_effect.setOpacity(1.0)
            self._settings_opacity = settings_effect
        except Exception:
            self._settings_opacity = None

        sidebar_layout.addWidget(settings_btn)
        # Attach a reference so the collapse toggle can hide/show it
        sidebar._settings_btn = settings_btn

        # Main content area (right side)
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        # Show the stacked pages in the main content area
        content_layout.addWidget(self.page_stack)

        # Ensure stack starts on the first page
        try:
            self.page_stack.setCurrentIndex(0)
        except Exception:
            pass

        main_layout.addWidget(sidebar, 0)
        main_layout.addWidget(content_area, 1)

    def _toggle_canvas_url_input(self, checked):
        self.canvas_url_input.setVisible(not checked)
        self._save_settings("use_default_url", checked)

    def _open_settings_dialog(self):
        """Show SettingsDialog and apply selected values back to the main UI."""
        try:
            # Pass current buckets into the settings dialog so the user can edit them
            current_buckets = self._load_settings_value('buckets', [k for k in ['past','undated','upcoming','future','ungraded']])
            dlg = SettingsDialog(parent=self, startup_checked=self.startup_checkbox.isChecked(), advanced_checked=self.advanced_toggle.isChecked(), current_buckets=current_buckets)
            result = dlg.exec()
            if result == QDialog.DialogCode.Accepted:
                # Apply startup setting
                try:
                    startup_val = getattr(dlg, 'startup_selected', dlg.startup_cb.isChecked())
                    self.startup_checkbox.setChecked(startup_val)
                    set_startup(startup_val)
                except Exception:
                    pass
                # Apply advanced flags (currently only show_advanced)
                try:
                    adv_flags = getattr(dlg, 'advanced_flags', {'show_advanced': dlg.adv_show_advanced.isChecked()})
                    adv_val = adv_flags.get('show_advanced', False)
                    self.advanced_toggle.setChecked(adv_val)
                    self._toggle_advanced(bool(adv_val))
                except Exception:
                    pass
                # Apply selected buckets
                try:
                    selected_buckets = getattr(dlg, 'selected_buckets', [])
                    self._save_settings('buckets', selected_buckets)
                except Exception:
                    pass
        except Exception as e:
            try:
                self.status_output.append(f"Could not open settings: {e}")
            except Exception:
                pass

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

    # Improve appearance on modern Windows: enable High-DPI scaling and use Fusion style
    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    
    # --- FIX: Use resource_path for font file ---
    font_path = resource_path("Figtree-VariableFont_wght.ttf")
    if os.path.exists(font_path): 
        QFontDatabase.addApplicationFont(font_path)
    else: 
        print("WARNING: Figtree-VariableFont_wght.ttf not found.")
    
    # Prefer the Fusion style for a consistent, modern cross-platform look
    try:
        app.setStyle('Fusion')
    except Exception:
        pass

    # Apply a complementary dark palette to match MODERN_QSS and avoid Windows 7 visuals
    try:
        palette = app.palette()
        palette.setColor(palette.ColorRole.Window, QColor(43, 43, 43))
        palette.setColor(palette.ColorRole.WindowText, QColor(240, 240, 240))
        palette.setColor(palette.ColorRole.Base, QColor(37, 37, 38))
        palette.setColor(palette.ColorRole.AlternateBase, QColor(60, 63, 65))
        palette.setColor(palette.ColorRole.ToolTipBase, QColor(240, 240, 240))
        palette.setColor(palette.ColorRole.ToolTipText, QColor(0, 0, 0))
        palette.setColor(palette.ColorRole.Text, QColor(240, 240, 240))
        palette.setColor(palette.ColorRole.Button, QColor(60, 63, 65))
        palette.setColor(palette.ColorRole.ButtonText, QColor(240, 240, 240))
        palette.setColor(palette.ColorRole.Highlight, QColor(0, 120, 215))
        palette.setColor(palette.ColorRole.HighlightedText, QColor(255, 255, 255))
        app.setPalette(palette)
    except Exception:
        pass

    # Set a modern default font (prefer Segoe UI on Windows)
    try:
        if sys.platform == 'win32':
            app.setFont(QFont('Segoe UI', 10))
        else:
            app.setFont(QFont('Figtree', 11))
    except Exception:
        pass

    # Try to apply qt-material for a polished cross-platform theme; fall back to our QSS.
    try:
        import qt_material
        try:
            qt_material.apply_stylesheet(app, theme='dark_cyan.xml')
            # Merge our small overrides on top so custom tweaks remain in effect.
            try:
                current = app.styleSheet() or ""
                app.setStyleSheet(current + "\n" + MODERN_QSS)
            except Exception:
                app.setStyleSheet(MODERN_QSS)
        except Exception:
            # If theme application fails, use our QSS
            app.setStyleSheet(MODERN_QSS)
    except Exception:
        # qt-material not installed — use the existing QSS
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