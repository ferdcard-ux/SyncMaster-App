
from PyQt6.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QFrame,
    QTextEdit, QSystemTrayIcon, QMessageBox, QScrollArea, QGridLayout, QSizePolicy, QStyle
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon
from ui.settings_dialog import SettingsDialog
from managers.rclone_service import RcloneServiceManager
import os
import time
import shutil
from html import escape

class MainWindow(QMainWindow):
    def __init__(self, config_manager, onedrive_manager, gdrive_manager, local_manager, version, tray, rclone_managers=None):
        super().__init__()
        self.config_manager = config_manager
        self.onedrive_manager = onedrive_manager
        self.gdrive_manager = gdrive_manager
        self.local_manager = local_manager
        self.version = version
        self.tray = tray
        self.rclone_managers = rclone_managers or []
        self.rclone_manager_map = {}
        self.sync_paused = False
        self._connected_rclone_names = set()
        self.notification_cooldown = 60
        self.last_notifications = {}
        self.display_names = {
            "local_sync": "Local (Rclone)",
            "gdrive": "Google Drive (Rclone)",
            "onedrive": "OneDrive (on-prem)"
        }
        
        self.setWindowTitle(f"Sync Master v{self.version} - Monitor en Tiempo Real")
        self.resize(900, 700)
        # Clean background and default text
        self.setStyleSheet("background-color: #ffffff; color: #333333; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;")
        
        # Icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets/logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # UI Elements storage
        self.status_labels = {}
        self.interval_labels = {}
        self.last_sync_labels = {}
        self.base_button_style = (
            "QPushButton { background-color: #011403; color: #ffffff; padding: 6px 12px; "
            "border: 1px solid #0a2a10; border-radius: 4px; text-align: center; }"
            "QPushButton:hover { background-color: #03380c; }"
            "QPushButton:focus { outline: none; border: 2px solid #2f7a3a; }"
            "QPushButton:pressed { background-color: #001c06; }"
        )
        self.icon_size = QSize(16, 16)
        
        self.setup_ui()
        self.connect_signals()
        self.reload_rclone_services(initial=True)
        
        # Start timers (initialize UI state)
        self.update_initial_info()
        self.onedrive_manager.start_timer()
        self.gdrive_manager.start_timer()
        self.local_manager.start_timer()
        for manager in self.rclone_managers:
            manager.start_timer()

        QTimer.singleShot(0, self.show_welcome_if_needed)

    def setup_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # No extra top bar; Info button lives in the bottom control bar.
        
        # 1. Dashboard Area (Top)
        dashboard_group = QFrame()
        dashboard_group.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 8px; margin-bottom: 10px;")
        dash_layout = QVBoxLayout()
        dashboard_group.setLayout(dash_layout)

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(10)
        self.cards_container.setLayout(self.cards_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_container)
        scroll.setStyleSheet("border: none;")

        dash_layout.addWidget(scroll)
        
        main_layout.addWidget(dashboard_group)
        
        # 2. Console Area (Bottom)
        console_label = QLabel("Registro de Actividad y Errores:")
        console_label.setStyleSheet("font-weight: bold; color: #444; margin-top: 5px;")
        main_layout.addWidget(console_label)
        
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("""
            QTextEdit {
                background-color: #fafafa;
                color: #222;
                font-family: 'Fira Code', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        main_layout.addWidget(self.console)
        
        # 3. Control Buttons
        btn_layout = QHBoxLayout()
        
        clean_btn = QPushButton("Limpiar Consola")
        clean_btn.clicked.connect(self.console.clear)
        clean_btn.setStyleSheet(self.base_button_style)
        clean_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))
        clean_btn.setIconSize(self.icon_size)
        btn_layout.addWidget(clean_btn)

        cache_btn = QPushButton("Limpiar Cache RClone")
        cache_btn.clicked.connect(self.clean_rclone_cache)
        cache_btn.setStyleSheet(self.base_button_style)
        cache_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        cache_btn.setIconSize(self.icon_size)
        btn_layout.addWidget(cache_btn)

        self.pause_btn = QPushButton("Pausar Sincronización")
        self.pause_btn.clicked.connect(self.toggle_syncs)
        self.pause_btn.setStyleSheet(self.base_button_style)
        self.pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.pause_btn.setIconSize(self.icon_size)
        btn_layout.addWidget(self.pause_btn)

        info_btn = QPushButton("Info")
        info_btn.clicked.connect(self.show_info)
        info_btn.setStyleSheet(self.base_button_style)
        info_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation))
        info_btn.setIconSize(self.icon_size)
        btn_layout.addWidget(info_btn)

        settings_btn = QPushButton("Configuración")
        settings_btn.clicked.connect(self.open_settings)
        settings_btn.setStyleSheet(self.base_button_style)
        settings_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        settings_btn.setIconSize(self.icon_size)
        btn_layout.addWidget(settings_btn)

        quit_btn = QPushButton("Salir")
        quit_btn.clicked.connect(self.close)
        quit_btn.setStyleSheet(self.base_button_style)
        quit_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        quit_btn.setIconSize(self.icon_size)
        btn_layout.addWidget(quit_btn)

        for i in range(btn_layout.count()):
            item = btn_layout.itemAt(i)
            if item and item.widget():
                item.widget().setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                btn_layout.setStretch(i, 1)

        main_layout.addLayout(btn_layout)

    def create_service_card(self, title, key, sync_callback):
        frame = QFrame()
        frame.setStyleSheet("background-color: #ffffff; border: 1px solid #eee; border-radius: 6px;")
        layout = QVBoxLayout()
        frame.setLayout(layout)
        
        # Title
        title_lbl = QLabel(f"<b>{title}</b>")
        title_lbl.setStyleSheet("color: #0056b3; font-size: 15px; margin-bottom: 5px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        # Status
        self.status_labels[key] = QLabel("Estado: Desconocido")
        layout.addWidget(self.status_labels[key])
        
        # Interval
        self.interval_labels[key] = QLabel("Intervalo: --")
        layout.addWidget(self.interval_labels[key])
        
        # Last Sync
        self.last_sync_labels[key] = QLabel("Última Sinc: Nunca")
        layout.addWidget(self.last_sync_labels[key])
        
        # Manual Sync Button
        sync_btn = QPushButton("Sincronizar Ahora")
        sync_btn.setStyleSheet(self.base_button_style + "QPushButton { margin-top: 5px; }")
        sync_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        sync_btn.setIconSize(self.icon_size)
        if sync_callback:
            sync_btn.clicked.connect(sync_callback)
        layout.addWidget(sync_btn)
        
        return frame

    def connect_signals(self):
        # Local
        self.local_manager.status_changed.connect(lambda s: self.update_status("local_sync", s))
        self.local_manager.log_message.connect(self.append_log)
        self.local_manager.sync_finished.connect(lambda t: self.update_last_sync("local_sync", t))
        
        # GDrive
        self.gdrive_manager.status_changed.connect(lambda s: self.update_status("gdrive", s))
        self.gdrive_manager.log_message.connect(self.append_log)
        self.gdrive_manager.sync_finished.connect(lambda t: self.update_last_sync("gdrive", t))
        
        # OneDrive
        self.onedrive_manager.status_changed.connect(lambda s: self.update_status("onedrive", s))
        self.onedrive_manager.log_message.connect(self.append_log)
        self.onedrive_manager.sync_finished.connect(lambda t: self.update_last_sync("onedrive", t))

    def connect_rclone_signals(self, manager, key):
        if manager.service_name in self._connected_rclone_names:
            return
        manager.status_changed.connect(lambda s, k=key: self.update_status(k, s))
        manager.log_message.connect(self.append_log)
        manager.sync_finished.connect(lambda t, k=key: self.update_last_sync(k, t))
        self._connected_rclone_names.add(manager.service_name)

    def build_service_cards(self):
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        self.status_labels = {}
        self.interval_labels = {}
        self.last_sync_labels = {}

        entries = [
            ("local_sync", "Local (Rclone)", self.local_manager.sync),
            ("gdrive", "Google Drive (Rclone)", self.gdrive_manager.sync),
            ("onedrive", "OneDrive (on-prem)", self.onedrive_manager.sync),
        ]

        for manager in self.rclone_managers:
            key = f"rclone:{manager.service_name}"
            entries.append((key, manager.service_name, manager.sync))
            self.display_names[key] = manager.service_name

        cols = 3
        for idx, (key, title, callback) in enumerate(entries):
            row = idx // cols
            col = idx % cols
            self.cards_layout.addWidget(self.create_service_card(title, key, callback), row, col)

    def reload_rclone_services(self, initial=False):
        services = self.config_manager.get("rclone_services", []) or []
        new_names = {s.get("name") for s in services if s.get("name")}

        if initial:
            if not self.rclone_managers:
                self.rclone_managers = [
                    RcloneServiceManager(self.config_manager, self.onedrive_manager.coordinator, name)
                    for name in new_names
                ]
        else:
            for manager in self.rclone_managers:
                if manager.service_name not in new_names:
                    manager.stop_timer()
                    if manager.service_name in self._connected_rclone_names:
                        self._connected_rclone_names.remove(manager.service_name)

            existing = {m.service_name: m for m in self.rclone_managers}
            self.rclone_managers = []
            for name in new_names:
                if name in existing:
                    self.rclone_managers.append(existing[name])
                else:
                    self.rclone_managers.append(RcloneServiceManager(self.config_manager, self.onedrive_manager.coordinator, name))

        self.rclone_manager_map = {m.service_name: m for m in self.rclone_managers}
        for manager in self.rclone_managers:
            self.connect_rclone_signals(manager, f"rclone:{manager.service_name}")

        self.build_service_cards()

    def update_initial_info(self):
        for key in list(self.interval_labels.keys()):
            if key in ["local_sync", "gdrive", "onedrive"]:
                conf = self.config_manager.get(key, {})
                interval = conf.get("interval_minutes", 15)
                enabled = conf.get("enabled", False)
            else:
                service_name = key.split("rclone:", 1)[1] if "rclone:" in key else key
                conf = self.get_rclone_service_config(service_name) or {}
                interval = conf.get("interval_minutes", 15)
                enabled = conf.get("enabled", True)

            self.interval_labels[key].setText(f"Intervalo: {interval} min")
            if not enabled:
                self.status_labels[key].setText("Estado: Desactivado")
                self.status_labels[key].setStyleSheet("color: #6c757d;")
            else:
                self.status_labels[key].setText("Estado: Activo")
                self.status_labels[key].setStyleSheet("color: #28a745; font-weight: bold;")

    def update_status(self, key, status):
        lbl = self.status_labels.get(key)
        if lbl:
            lbl.setText(f"Estado: {status}")
            if "Error" in status:
                lbl.setStyleSheet("color: #dc3545; font-weight: bold;")
            elif "Sincronizando" in status:
                lbl.setStyleSheet("color: #fd7e14; font-weight: bold;")
            elif "Desactivado" in status or "Detenido" in status:
                lbl.setStyleSheet("color: #6c757d;")
            else:
                lbl.setStyleSheet("color: #28a745; font-weight: bold;")

            self.maybe_notify_status(key, status)

    def update_last_sync(self, key, timestamp):
        lbl = self.last_sync_labels.get(key)
        if lbl:
            from datetime import datetime
            dt = datetime.fromtimestamp(timestamp)
            time_str = dt.strftime("%H:%M:%S")
            lbl.setText(f"Última Sinc: {time_str}")

    def append_log(self, message):
        # Escape HTML special characters
        safe_msg = escape(message)
        
        # Detect errors and highlight in red
        error_keywords = ["Error", "Failed", "Critico", "Aborted", "Unreachable", "Connection"]
        is_error = any(key.lower() in message.lower() for key in error_keywords)
        
        if is_error:
            html_msg = f"<font color='#dc3545'><b>{safe_msg}</b></font>"
            self.console.append(html_msg)
        else:
            self.console.append(message)

        self.maybe_notify_log(message)
            
        # Scroll to bottom
        sb = self.console.verticalScrollBar()
        sb.setValue(sb.maximum())

    def open_settings(self):
        dialog = SettingsDialog(self.config_manager, self)
        if dialog.exec():
            # Refresh info and restart timers
            self.reload_rclone_services()
            self.update_initial_info()
            self.onedrive_manager.start_timer()
            self.gdrive_manager.start_timer()
            self.local_manager.start_timer()
            for manager in self.rclone_managers:
                manager.start_timer()

    def clean_rclone_cache(self):
        answer = QMessageBox.question(
            self,
            "Limpiar Cache RClone",
            "Se eliminará la caché de rclone bisync. Esto forzará una re-sincronización completa y puede tardar más tiempo.\n\n¿Deseas continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        cache_dir = os.path.expanduser("~/.cache/rclone/bisync")
        if os.path.isdir(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
            self.append_log("RClone: Caché de bisync eliminada. Se forzará re-sincronización.")
        else:
            self.append_log("RClone: Caché de bisync no encontrada. Se forzará re-sincronización.")

        self.local_manager.force_resync()
        self.gdrive_manager.force_resync()
        for manager in self.rclone_managers:
            manager.force_resync()

        if self.tray:
            self.tray.show_message("Sync Master", "Cache RClone limpiada. Re-sincronización programada.", QSystemTrayIcon.MessageIcon.Information)

    def toggle_syncs(self):
        if not self.sync_paused:
            self.onedrive_manager.stop_timer()
            self.gdrive_manager.stop_timer()
            self.local_manager.stop_timer()
            for manager in self.rclone_managers:
                manager.stop_timer()
            self.sync_paused = True
            self.pause_btn.setText("Reanudar Sincronización")
            self.update_pause_button_style()
            self.append_log("Sync Master: Sincronizaciones en pausa.")
        else:
            self.onedrive_manager.start_timer()
            self.gdrive_manager.start_timer()
            self.local_manager.start_timer()
            for manager in self.rclone_managers:
                manager.start_timer()
            self.sync_paused = False
            self.pause_btn.setText("Pausar Sincronización")
            self.update_pause_button_style()
            self.append_log("Sync Master: Sincronizaciones reanudadas.")

    def update_pause_button_style(self):
        if self.sync_paused:
            self.pause_btn.setStyleSheet(
                "QPushButton { background-color: #F5F135; color: #1f1f1f; padding: 6px 12px; "
                "border: 1px solid #d4d129; border-radius: 4px; text-align: center; }"
                "QPushButton:hover { background-color: #e0d600; }"
                "QPushButton:focus { outline: none; border: 2px solid #b9b418; }"
                "QPushButton:pressed { background-color: #d9d432; }"
            )
            self.pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.pause_btn.setIconSize(self.icon_size)
        else:
            self.pause_btn.setStyleSheet(self.base_button_style)
            self.pause_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.pause_btn.setIconSize(self.icon_size)

    def show_welcome_if_needed(self):
        gen_conf = self.config_manager.get("general", {})
        if gen_conf.get("welcome_shown", False):
            return

        message = (
            f"Sync Master - Versión: {self.version}\n"
            "Desarrollador: FerDev\n"
            "Contacto: ferdcard@gmail.com\n\n"
            "Importante: Sync Master utiliza los servicios de software de terceros como RClone y el cliente de OneDrive "
            "para ejecutar la configuración y sincronización de directorios. Es indispensable que dichos servicios se "
            "encuentren instalados en su sistema para el correcto funcionamiento de esta app.\n\n"
            "El desarrollador de Sync Master no es responsable por el uso y/o disponibilidad del software adicional anteriormente mencionado."
        )
        QMessageBox.information(self, "Bienvenido a Sync Master", message)
        gen_conf["welcome_shown"] = True
        self.config_manager.set("general", gen_conf)

    def show_info(self):
        info = QMessageBox(self)
        info.setWindowTitle("Información de la App")
        info.setText(
            "Sync Master\n"
            f"Versión: {self.version}\n"
            "Fecha de actualización: 2026-03-13\n"
            "Desarrollador: FerDev\n"
            "Contacto: ferdcard@gmail.com\n\n"
            "Sync Master centraliza la sincronización entre carpetas locales y servicios en la nube, "
            "ofreciendo monitoreo en tiempo real, recuperación ante fallos y herramientas de mantenimiento."
        )
        info.exec()

    def get_rclone_service_config(self, service_name):
        services = self.config_manager.get("rclone_services", []) or []
        for service in services:
            if service.get("name") == service_name:
                return service
        return None

    def maybe_notify_status(self, key, status):
        if not self.tray:
            return

        level = None
        status_lower = status.lower()
        if "error" in status_lower or "sin conexión" in status_lower:
            level = "critical"
        elif "en espera" in status_lower or "resync" in status_lower:
            level = "warning"

        if not level:
            return

        display_name = self.display_names.get(key, key)
        message = f"{display_name}: {status}"
        self.send_notification(level, "Sync Master", message, f"{level}:{key}")

    def maybe_notify_log(self, message):
        if not self.tray:
            return

        msg_lower = message.lower()
        if "re-sincronización" in msg_lower or "resync" in msg_lower:
            self.send_notification("warning", "Sync Master", message, "warning:log")
        elif "error crítico" in msg_lower or "critico" in msg_lower:
            self.send_notification("critical", "Sync Master", message, "critical:log")

    def send_notification(self, level, title, message, dedupe_key=None):
        now = time.time()
        key = dedupe_key or f"{level}:{title}"
        last_time = self.last_notifications.get(key, 0)
        if now - last_time < self.notification_cooldown:
            return
        self.last_notifications[key] = now

        icon = QSystemTrayIcon.MessageIcon.Information
        if level == "critical":
            icon = QSystemTrayIcon.MessageIcon.Critical
        elif level == "warning":
            icon = QSystemTrayIcon.MessageIcon.Warning

        self.tray.show_message(title, message, icon)
