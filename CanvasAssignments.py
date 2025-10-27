import sys
import os
from datetime import datetime
import json
import time
import schedule
import re # Import regex for parsing status messages
import locale # --- NEW: For language detection ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QDialog,
    QLabel, QLineEdit, QPushButton, QTextEdit, QProgressBar,
    QSystemTrayIcon, QMenu, QTimeEdit, QCheckBox, QTabWidget, QTabBar
)
from PyQt6.QtGui import QIcon, QAction, QFontDatabase, QPixmap, QPainter, QColor, QPolygonF
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTime, QPointF, QSize

from canvas_notion_calendar_db_v1 import get_canvas_assignments, add_to_notion

# --- NEW: Language Detection and Translation Strings ---
try:
    # Set the locale to the user's default setting to initialize
    locale.setlocale(locale.LC_ALL, '')
    # Get the language code from the current locale settings
    lang_code_full = locale.getlocale(locale.LC_CTYPE)[0]
    
    if lang_code_full:
        LANG_CODE = lang_code_full[:2] # Get 'en' from 'en_US'
        if LANG_CODE not in ['en', 'es']:
            LANG_CODE = 'en' # Default to English if not 'en' or 'es'
    else:
        LANG_CODE = 'en' # Default if getlocale returns None
except Exception:
    LANG_CODE = 'en' # Default to English if detection fails

HELP_HTML_EN = """
<body style='color: #f0f0f0; font-size: 14px;'>
<h2>How to get your API Keys</h2>
<p>Follow these steps to get the 3 required keys for the app.</p>
<hr style='border-color: #555;'>
<h3>1. Canvas API Key</h3>
<ol>
    <li>Log in to Canvas.</li>
    <li>In the left-hand navigation, click <b>Account</b>, then <b>Settings</b>.</li>
    <li>Scroll down to the <b>Approved Integrations</b> section.</li>
    <li>Click the <b>+ New Access Token</b> button.</li>
    <li>Give it a <b>Purpose</b> (e.g., "Notion Sync") and an <b>Expires</b> date (optional, but recommended).</li>
    <li>Click <b>Generate Token</b>.</li>
    <li><b>IMPORTANT:</b> Copy the generated token immediately. You will not be able to see it again.</li>
    <li>Paste this token into the "Canvas API Key" field.</li>
</ol>
<hr style='border-color: #555;'>
<h3>2. Notion API Key (Integration)</h3>
<ol>
    <li>Go to <a style='color: #00aaff;' href='https://www.notion.so/my-integrations'>www.notion.so/my-integrations</a>.</li>
    <li>Click the <b>+ New integration</b> button.</li>
    <li>Give it a <b>Name</b> (e.g., "Canvas Sync").</li>
    <li>Select the <b>Workspace</b> where your database is located.</li>
    <li>Under <b>Capabilities</b>, make sure it has <b>Read content</b>, <b>Update content</b>, and <b>Insert content</b> permissions.</li>
    <li>Click <b>Submit</b>.</li>
    <li>On the next screen, copy the <b>Internal Integration Token</b> (it starts with <code>secret_...</code>).</li>
    <li>Paste this token into the "Notion API Key" field.</li>
</ol>
<hr style='border-color: #555;'>
<h3>3. Notion Database ID</h3>
<ol>
    <li>Create a new <b>Database - Full page</b> in Notion.</li>
    <li><b>CRITICAL:</b> Your database <b>MUST</b> have the following properties (case-sensitive):
        <ul>
            <li><b>Name</b> (This must be the default 'Title' property)</li>
            <li><b>Due Date</b> (A 'Date' property)</li>
            <li><b>Course</b> (A 'Rich Text' or 'Text' property)</li>
            <li><b>URL</b> (A 'URL' property)</li>
        </ul>
    </li>
    <li>
        <b>Share the database with your integration:</b>
        <ul>
            <li>Click the <b>...</b> icon in the top-right corner of your database page.</li>
            <li>Click <b>+ Add connections</b> (or <b>+ Invite</b>).</li>
            <li>Find and select the integration you created in Step 2 (e.g., "Canvas Sync").</li>
            <li>Ensure it has "Can edit" permissions.</li>
        </ul>
    </li>
    <li>
        <b>Get the Database ID:</b>
        <ul>
            <li>Open your database in the Notion app or in your browser.</li>
            <li>Copy the URL from your browser's address bar.</li>
            <li><b>Easy Way:</b> Paste the <b>full URL</b> into the "Notion Database ID" field. The app will find the ID for you.</li>
            <li><b>Manual Way:</b> The URL will look like this:<br>
                <code>https://www.notion.so/YOUR_WORKSPACE/<b>DATABASE_ID</b>?v=...</code><br>
                The <b>DATABASE_ID</b> is the long string (32 characters) between the <code>/</code> and the <code>?</code>. Copy <b>only</b> this ID.
            </li>
        </ul>
    </li>
</ol>
</body>
"""

HELP_HTML_ES = """
<body style='color: #f0f0f0; font-size: 14px;'>
<h2>Cómo obtener tus Claves API</h2>
<p>Sigue estos pasos para obtener las 3 claves requeridas por la aplicación.</p>
<hr style='border-color: #555;'>
<h3>1. Clave API de Canvas</h3>
<ol>
    <li>Inicia sesión en Canvas.</li>
    <li>En el menú de navegación izquierdo, haz clic en <b>Cuenta</b>, luego en <b>Configuración</b>.</li>
    <li>Desplázate hacia abajo hasta la sección <b>Integraciones aprobadas</b>.</li>
    <li>Haz clic en el botón <b>+ Nuevo Token de Acceso</b>.</li>
    <li>Asígnale un <b>Propósito</b> (ej. "Sincronizar con Notion") y una fecha de <b>Expiración</b> (opcional, pero recomendado).</li>
    <li>Haz clic en <b>Generar Token</b>.</li>
    <li><b>IMPORTANTE:</b> Copia el token generado inmediatamente. No podrás volver a verlo.</li>
    <li>Pega este token en el campo "Clave API de Canvas".</li>
</ol>
<hr style='border-color: #555;'>
<h3>2. Clave API de Notion (Integración)</h3>
<ol>
    <li>Ve a <a style='color: #00aaff;' href='https://www.notion.so/my-integrations'>www.notion.so/my-integrations</a>.</li>
    <li>Haz clic en el botón <b>+ Nueva integración</b>.</li>
    <li>Asígnale un <b>Nombre</b> (ej. "Canvas Sync").</li>
    <li>Selecciona el <b>Espacio de trabajo</b> donde se encuentra tu base de datos.</li>
    <li>Bajo <b>Capacidades</b>, asegúrate de que tenga permisos para <b>Leer contenido</b>, <b>Actualizar contenido</b> e <b>Insertar contenido</b>.</li>
    <li>Haz clic en <b>Enviar</b>.</li>
    <li>En la siguiente pantalla, copia el <b>Token de Integración Interna</b> (comienza con <code>secret_...</code>).</li>
    <li>Pega este token en el campo "Clave API de Notion".</li>
</ol>
<hr style='border-color: #555;'>
<h3>3. ID de Base de Datos de Notion</h3>
<ol>
    <li>Crea una nueva <b>Base de datos - Página completa</b> en Notion.</li>
    <li><b>CRÍTICO:</b> Tu base de datos <b>DEBE</b> tener las siguientes propiedades (sensible a mayúsculas):
        <ul>
            <li><b>Name</b> (Esta debe ser la propiedad 'Title' por defecto)</li>
            <li><b>Due Date</b> (Una propiedad de 'Fecha')</li>
            <li><b>Course</b> (Una propiedad 'Rich Text' o 'Texto')</li>
            <li><b>URL</b> (Una propiedad 'URL')</li>
        </ul>
    </li>
    <li>
        <b>Comparte la base de datos con tu integración:</b>
        <ul>
            <li>Haz clic en el ícono <b>...</b> en la esquina superior derecha de tu página de base de datos.</li>
            <li>Haz clic en <b>+ Añadir conexiones</b> (o <b>+ Invitar</b>).</li>
            <li>Busca y selecciona la integración que creaste en el Paso 2 (ej. "Canvas Sync").</li>
            <li>Asegúrate de que tenga permisos de "Puede editar".</li>
        </ul>
    </li>
    <li>
        <b>Obtén el ID de la Base de Datos:</b>
        <ul>
            <li>Abre tu base de datos en la app de Notion o en tu navegador.</li>
            <li>Copia la URL de la barra de direcciones de tu navegador.</li>
            <li><b>Forma Fácil:</b> Pega la <b>URL completa</b> en el campo "ID de Base de Datos de Notion". La app extraerá el ID por ti.</li>
            <li><b>Forma Manual:</b> La URL se verá así:<br>
                <code>https://www.notion.so/TU_ESPACIO_TRABAJO/<b>ID_DE_BASE_DE_DATOS</b>?v=...</code><br>
                El <b>ID_DE_BASE_DE_DATOS</b> es la cadena larga (32 caracteres) entre la <code>/</code> y el <code>?</code>. Copia <b>solo</b> este ID.
            </li>
        </ul>
    </li>
</ol>
</body>
"""

TRANSLATIONS = {
    'en': {
        'window_title': "Canvas to Notion Sync",
        'canvas_key_label': "Canvas API Key:",
        'canvas_key_placeholder': "Enter Canvas API Key",
        'notion_key_label': "Notion API Key:",
        'notion_key_placeholder': "Enter Notion API Key",
        'notion_db_label': "Notion Database ID:",
        'notion_db_placeholder': "Enter Notion Database ID or URL",
        'help_tooltip': "Help: How to get API Keys",
        'run_sync_button': "Run Manual Sync",
        'tab_credentials': "Credentials & Sync",
        'tab_scheduler': "Scheduler",
        'scheduler_label': "Set daily sync time (24-hour format):",
        'startup_checkbox': "Start automatically on login",
        'sync_error_all_fields': "Error: All fields are required. Click the help button for setup instructions.",
        'tray_tooltip': "Canvas to Notion Sync",
        'tray_run_sync': "Run Manual Sync",
        'tray_show_window': "Show Window",
        'tray_quit': "Quit",
        'help_title': "API Key Setup Guide",
        'help_close': "Close",
        'help_switch_button': "Ver en Español",
        'help_html': HELP_HTML_EN,
        'easter_egg_title': "Special Thanks!", # <-- ADDED
        'easter_egg_message': "Thank you DOer for using the app" # <-- ADDED
    },
    'es': {
        'window_title': "Sincronización de Canvas a Notion",
        'canvas_key_label': "Clave API de Canvas:",
        'canvas_key_placeholder': "Ingresa la Clave API de Canvas",
        'notion_key_label': "Clave API de Notion:",
        'notion_key_placeholder': "Ingresa la Clave API de Notion",
        'notion_db_label': "ID de Base de Datos de Notion:",
        'notion_db_placeholder': "Ingresa el ID o la URL de la Base de Datos de Notion",
        'help_tooltip': "Ayuda: Cómo obtener Claves API",
        'run_sync_button': "Ejecutar Sincronización Manual",
        'tab_credentials': "Credenciales y Sincronización",
        'tab_scheduler': "Programador",
        'scheduler_label': "Establecer hora de sincronización diaria (formato 24h):",
        'startup_checkbox': "Iniciar automáticamente al iniciar sesión",
        'sync_error_all_fields': "Error: Todos los campos son requeridos. Haz clic en el botón de ayuda para instrucciones.",
        'tray_tooltip': "Sincronización de Canvas a Notion",
        'tray_run_sync': "Ejecutar Sincronización Manual",
        'tray_show_window': "Mostrar Ventana",
        'tray_quit': "Salir",
        'help_title': "Guía de Configuración de Claves API",
        'help_close': "Cerrar",
        'help_switch_button': "View in English",
        'help_html': HELP_HTML_ES,
        'easter_egg_title': "¡Gracias Especiales!", # <-- ADDED
        'easter_egg_message': "Gracias DOer por usar la app" # <-- ADDED
    }
}

T = TRANSLATIONS[LANG_CODE] # Global translator object

# --- MODERN STYLESHEET (QSS) ---
MODERN_QSS = """
QWidget {
    background-color: #2b2b2b;
    color: #f0f0f0;
    font-family: 'Figtree', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', sans-serif;
    font-size: 14px;
}
QTabWidget::pane {
    border: 1px solid #555;
    border-top: none;
}
QTabBar::tab {
    background: #2b2b2b;
    border: 1px solid #555;
    border-bottom: none;
    padding: 8px 15px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}
QTabBar::tab:selected {
    background: #3c3f41;
    border-color: #555;
}
QTabBar::tab:!selected {
    margin-top: 2px;
}
QLabel { background-color: transparent; }
QLineEdit { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; padding: 6px; }
QLineEdit:focus { border: 1px solid #0078d7; }
QPushButton { background-color: #0078d7; color: white; font-weight: bold; border: none; border-radius: 4px; padding: 8px 16px; }
QPushButton:hover { background-color: #005a9e; }
QPushButton:disabled { background-color: #4f4f4f; color: #999; }
/* --- NEW STYLE for the help button --- */
QPushButton#HelpButton {
    background-color: #4a4a4a;
    font-weight: bold;
    font-size: 16px;
    color: #f0f0f0;
    /* Make it circular */
    border-radius: 15px; /* (width/2) or (height/2) */
    /* Remove padding that might make it non-circular */
    padding: 0px;
    /* Ensure text is centered */
    text-align: center;
    /* Remove border */
    border: none;
}
QPushButton#HelpButton:hover {
    background-color: #5a5a5a;
}
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
QCheckBox::indicator:checked { background-color: #0078d7; image: url(icon:checkmark.png); }
/* Style for the help dialog text */
QTextEdit#HelpText {
    background-color: #2b2b2b;
    border: none;
    padding: 10px;
}
"""

# --- EASTER EGG: Custom Popup Dialog ---
class EasterEggPopup(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T['easter_egg_title']) # <-- MODIFIED
        self.setFixedSize(300, 300) # Adjust size to fit text and image
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        
        # Thank you message
        message_label = QLabel(T['easter_egg_message']) # <-- MODIFIED
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(message_label)
        
        # Image display
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # This is where the image from the prompt will be loaded.
        # Ensure 'doer_logo.png' is in the same directory as your script
        image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doer_logo.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            # Scale the pixmap to fit within the dialog, keeping aspect ratio
            scaled_pixmap = pixmap.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(scaled_pixmap)
        else:
            image_label.setText("Image not found: doer_logo.png")
            image_label.setStyleSheet("color: red; font-size: 12px;")
            
        layout.addWidget(image_label)

# --- EASTER EGG FIX: Custom QTabBar to correctly detect clicks ---
class EasterEggTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scheduler_clicks = 0
        self._last_click_time = 0

    def mousePressEvent(self, event):
        # Allow the default handler to run first to handle normal tab switching
        super().mousePressEvent(event)
        
        tab_index = self.tabAt(event.pos())
        # Index 1 is the "Scheduler" tab
        if tab_index == 1:
            current_time = time.time()
            
            # If clicks are more than 3 seconds apart, reset the counter
            if current_time - self._last_click_time > 3.0:
                self._scheduler_clicks = 1 # Start count at 1
            else:
                self._scheduler_clicks += 1
            
            self._last_click_time = current_time
            
            if self._scheduler_clicks >= 5:
                self._scheduler_clicks = 0 # Reset after triggering
                # self.window() gets the main application window to use as a parent
                popup = EasterEggPopup(self.window())
                popup.exec()

# --- MODIFIED: Help Dialog for API Keys ---
class HelpDialog(QDialog):
    def __init__(self, lang='en', parent=None): # Accept auto-detected lang
        super().__init__(parent)
        self.setWindowTitle(T['help_title']) # Title in auto-detected lang
        self.setModal(True)
        self.setMinimumSize(600, 500)
        
        self.current_lang = lang # Store the initial lang

        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setObjectName("HelpText") # For styling
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        
        # --- NEW: Button Layout ---
        button_layout = QHBoxLayout()
        
        # Language Toggle Button
        self.lang_toggle_button = QPushButton() # Text will be set by _update_content
        self.lang_toggle_button.clicked.connect(self._toggle_language)
        button_layout.addWidget(self.lang_toggle_button)
        
        button_layout.addStretch() # Push close button to the right
        
        # Close Button
        close_button = QPushButton(T['help_close']) # Close button in auto-detected lang
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
        
        # Call after all UI elements are created to set initial state
        self._update_content()

    def _update_content(self):
        """Sets the text edit content and button text based on self.current_lang."""
        if self.current_lang == 'en':
            self.text_edit.setHtml(HELP_HTML_EN)
            # When in English, button shows Spanish option
            self.lang_toggle_button.setText(TRANSLATIONS['en']['help_switch_button'])
        else: # 'es'
            self.text_edit.setHtml(HELP_HTML_ES)
            # When in Spanish, button shows English option
            self.lang_toggle_button.setText(TRANSLATIONS['es']['help_switch_button'])

    def _toggle_language(self):
        """Switches the language and updates content."""
        self.current_lang = 'es' if self.current_lang == 'en' else 'en'
        self._update_content()

    def _get_help_html(self):
        # This method is no longer needed
        pass


# --- SyncThread class remains unchanged ---
class SyncThread(QThread):
    update_status = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    def __init__(self, canvas_key: str, notion_key: str, notion_db_id: str):
        super().__init__()
        self.canvas_key = canvas_key
        self.notion_key = notion_key
        self.notion_db_id = notion_db_id

    def run(self):
        try:
            self.update_status.emit("Starting sync process...")
            self.update_progress.emit(5)
            self.update_status.emit("Fetching assignments from Canvas (concurrently)...")
            assignments = get_canvas_assignments(self.canvas_key, self.update_status.emit)
            if not assignments:
                self.update_status.emit("No new assignments found or Canvas fetch failed.")
                self.update_progress.emit(100)
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

            add_to_notion(self.notion_key, self.notion_db_id, assignments, status_and_progress_callback)
            self.update_status.emit("Sync completed successfully.")
            self.update_progress.emit(100)
        except Exception as e:
            self.update_status.emit(f"An unexpected error occurred during sync: {e}")
            self.update_progress.emit(0)

# --- Main application class ---
class CanvasNotionSyncApp(QWidget):
    def __init__(self):
        super().__init__()
        self.lang = LANG_CODE # Store lang
        self.setWindowTitle(T['window_title']); self.resize(640, 500) # Use translation
        self.credentials_file = "credentials.json"
        self._setup_ui()
        self._load_settings()

    def closeEvent(self, event):
        event.ignore(); self.hide()

    def _save_settings(self, key, value):
        data = {}
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r') as f: data = json.load(f)
            except (json.JSONDecodeError, IOError): pass
        data[key] = value
        with open(self.credentials_file, 'w') as f: json.dump(data, f, indent=4)

    def _load_settings(self):
        if not os.path.exists(self.credentials_file): return
        try:
            with open(self.credentials_file, 'r') as f: data = json.load(f)
            self.canvas_input.setText(data.get("canvas_key", ""))
            self.notion_key_input.setText(data.get("notion_key", ""))
            self.notion_db_input.setText(data.get("notion_db_id", ""))
            sync_time_str = data.get('sync_time', "23:59")
            h, m = map(int, sync_time_str.split(':'))
            self.time_edit.setTime(QTime(h, m))
            self.startup_checkbox.setChecked(is_startup_enabled())
        except Exception: pass

    # --- NEW: Method to show the help dialog ---
    def _show_help_dialog(self):
        dialog = HelpDialog(lang=self.lang, parent=self) # Pass lang
        dialog.exec()

    # --- NEW: Method to handle Notion DB ID input ---
    def _on_notion_input_changed(self, text):
        # Regex to find a Notion URL and extract the 32-char DB ID
        match = re.search(r"notion\.so/(?:[^/]+/)?([a-f0-9]{32})", text)
        if match:
            db_id = match.group(1)
            # Temporarily disconnect signal to prevent infinite loop
            self.notion_db_input.textChanged.disconnect(self._on_notion_input_changed)
            # Set the text to *only* the ID
            self.notion_db_input.setText(db_id)
            # Reconnect signal
            self.notion_db_input.textChanged.connect(self._on_notion_input_changed)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        tabs = QTabWidget()
        
        # --- EASTER EGG FIX: Replace the default tab bar with our custom one ---
        tabs.setTabBar(EasterEggTabBar())

        tabs.tabBar().setExpanding(True)
        tabs.setStyleSheet("""
            QTabBar::tab {
                min-width: 200px;
                padding: 6px 8px;
                font-size: 13px;
                white-space: normal;
            }
            QTabWidget::pane {
                border-top: 1px solid #555;
            }
        """)
        
        credentials_tab = QWidget()
        cred_layout = QVBoxLayout(credentials_tab)
        # --- MODIFIED: Use translations for placeholders and labels ---
        self.canvas_input=QLineEdit(placeholderText=T['canvas_key_placeholder'],echoMode=QLineEdit.EchoMode.Password)
        self.notion_key_input=QLineEdit(placeholderText=T['notion_key_placeholder'],echoMode=QLineEdit.EchoMode.Password)
        self.notion_db_input=QLineEdit(placeholderText=T['notion_db_placeholder'])
        # --- NEW: Connect signal for auto-filtering ---
        self.notion_db_input.textChanged.connect(self._on_notion_input_changed)
        
        # --- NEW: Help Button ---
        self.help_button = QPushButton("?") # Changed text
        self.help_button.setObjectName("HelpButton") # For styling
        self.help_button.setFixedSize(30, 30) # Set fixed size for circle
        self.help_button.setToolTip(T['help_tooltip']) # Use translation
        self.help_button.clicked.connect(self._show_help_dialog)
        
        self.run_button=QPushButton(T['run_sync_button']) # Use translation
        self.progress_bar=QProgressBar(minimum=0,maximum=100,value=0)
        self.status_output=QTextEdit(readOnly=True)
        
        cred_layout.addWidget(QLabel(T['canvas_key_label'])); cred_layout.addWidget(self.canvas_input) # Use translation
        cred_layout.addWidget(QLabel(T['notion_key_label'])); cred_layout.addWidget(self.notion_key_input) # Use translation
        cred_layout.addWidget(QLabel(T['notion_db_label'])); cred_layout.addWidget(self.notion_db_input) # Use translation
        
        cred_layout.addSpacing(10) # Add a little space
        cred_layout.addWidget(self.run_button)
        cred_layout.addWidget(self.progress_bar)
        cred_layout.addWidget(self.status_output)
        cred_layout.addStretch() # Pushes help button to the bottom
        
        # --- NEW: Layout for Help Button ---
        help_layout = QHBoxLayout()
        help_layout.addStretch() # Pushes button to the right
        help_layout.addWidget(self.help_button)
        
        cred_layout.addLayout(help_layout) # Add the horizontal layout to the bottom
        
        scheduler_tab = QWidget()
        sched_layout = QVBoxLayout(scheduler_tab)
        sched_layout.addWidget(QLabel(T['scheduler_label'])) # Use translation
        self.time_edit = QTimeEdit(); self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.timeChanged.connect(lambda time: self._save_settings('sync_time', time.toString("HH:mm")))
        sched_layout.addWidget(self.time_edit)
        self.startup_checkbox = QCheckBox(T['startup_checkbox']) # Use translation
        self.startup_checkbox.stateChanged.connect(lambda state: set_startup(state == Qt.CheckState.Checked.value))
        sched_layout.addWidget(self.startup_checkbox)
        sched_layout.addStretch()
        
        tabs.addTab(credentials_tab, T['tab_credentials']) # Use translation
        tabs.addTab(scheduler_tab, T['tab_scheduler']) # Use translation
        main_layout.addWidget(tabs)

    def _on_run_sync(self):
        cred_data = {
            "canvas_key": self.canvas_input.text(), 
            "notion_key": self.notion_key_input.text()
        }
        # Special handling for Notion DB ID to filter URL
        notion_db_input_text = self.notion_db_input.text().strip()
        match = re.search(r"notion\.so/(?:[^/]+/)?([a-f0-9]{32})", notion_db_input_text)
        if match:
            notion_db_id = match.group(1)
            # Update the text field to show the clean ID
            self.notion_db_input.textChanged.disconnect(self._on_notion_input_changed)
            self.notion_db_input.setText(notion_db_id)
            self.notion_db_input.textChanged.connect(self._on_notion_input_changed)
        else:
            notion_db_id = notion_db_input_text

        cred_data["notion_db_id"] = notion_db_id
        
        # Save all settings, including the cleaned ID
        for key, value in cred_data.items(): self._save_settings(key, value.strip())
        
        canvas_key=cred_data["canvas_key"].strip()
        notion_key=cred_data["notion_key"].strip()
        # notion_db_id is already cleaned
        
        if not all([canvas_key,notion_key,notion_db_id]):
            # --- MODIFIED: Use translation ---
            self.status_output.append(T['sync_error_all_fields'])
            return
        self.run_button.setEnabled(False);self.status_output.clear();self.progress_bar.setValue(0)
        self.sync_thread=SyncThread(canvas_key,notion_key,notion_db_id)
        self.sync_thread.update_status.connect(self.status_output.append)
        self.sync_thread.update_progress.connect(self.progress_bar.setValue)
        self.sync_thread.finished.connect(lambda:self.run_button.setEnabled(True))
        self.sync_thread.start()

# --- Platform-specific and background functions (Unchanged) ---
APP_NAME = "CanvasNotionSync"
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

script_dir = os.path.dirname(os.path.abspath(__file__)); log_file_path = os.path.join(script_dir, 'sync_log.txt'); credentials_file = os.path.join(script_dir, "credentials.json")
def log_message(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); log_entry = f"[{timestamp}] {message}"; print(log_entry)
    with open(log_file_path, 'a', encoding='utf-8') as f: f.write(log_entry + '\n')
def run_background_sync():
    log_message("--- Triggering Scheduled Sync ---")
    if not os.path.exists(credentials_file): log_message("ERROR: credentials.json not found."); return
    try:
        with open(credentials_file, 'r') as f: creds = json.load(f)
        canvas_key = creds['canvas_key']; notion_key = creds['notion_key']; notion_db_id = creds['notion_db_id']
        assignments = get_canvas_assignments(canvas_key, log_message)
        add_to_notion(notion_key, notion_db_id, assignments, log_message)
        log_message("--- Scheduled Sync Finished ---")
    except (KeyError, json.JSONDecodeError): log_message("ERROR: credentials.json is missing keys or is corrupt.")
    except Exception as e: log_message(f"An error occurred during scheduled sync: {e}")
def start_scheduler_daemon():
    sync_time = "23:59"
    if os.path.exists(credentials_file):
        try:
            with open(credentials_file, 'r') as f: creds = json.load(f); sync_time = creds.get('sync_time', '23:59')
        except (json.JSONDecodeError, IOError): pass
    log_message(f"Scheduler daemon started. Sync scheduled for {sync_time} daily.")
    schedule.every().day.at(sync_time).do(run_background_sync)
    while True: schedule.run_pending(); time.sleep(60)

# --- Main execution block (Unchanged) ---
if __name__ == "__main__":
    if '--daemon' in sys.argv: start_scheduler_daemon(); sys.exit()
    elif '--background' in sys.argv: run_background_sync(); sys.exit()
    
    app = QApplication(sys.argv)
    
    font_path = os.path.join(script_dir, "Figtree-VariableFont_wght.ttf")
    if os.path.exists(font_path): QFontDatabase.addApplicationFont(font_path)
    else: print("WARNING: Figtree-VariableFont_wght.ttf not found.")
    
    app.setStyleSheet(MODERN_QSS)
    app.setQuitOnLastWindowClosed(False)

    window = CanvasNotionSyncApp()
    icon_path = os.path.join(script_dir, "icon.png")
    if not os.path.exists(icon_path): print("ERROR: icon.png not found!"); sys.exit(1)
    
    # --- MODIFIED: Use translations for tray menu ---
    tray_icon = QSystemTrayIcon(QIcon(icon_path), parent=app)
    tray_icon.setToolTip(T['tray_tooltip'])
    menu = QMenu(); run_sync_action = QAction(T['tray_run_sync'], app)
    run_sync_action.triggered.connect(window._on_run_sync)
    menu.addAction(run_sync_action); menu.addSeparator()
    
    show_action = QAction(T['tray_show_window'], app)
    show_action.triggered.connect(window.show)
    menu.addAction(show_action)
    menu.addSeparator()
    
    quit_action = QAction(T['tray_quit'], app)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)
    
    tray_icon.setContextMenu(menu)
    tray_icon.show()
    
    if not os.path.exists(credentials_file): window.show()
    
    sys.exit(app.exec())

