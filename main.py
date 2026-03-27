# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

# Sync Master main entry point.
# Copyright 2026 FerDev

import sys
import os
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon
from PyQt6.QtGui import QIcon
from ui.main_window import MainWindow
from ui.tray_icon import SystemTray
from managers.config import ConfigManager
from managers.onedrive import OneDriveManager
from managers.gdrive import GDriveManager
from managers.local_sync import LocalSyncManager
from managers.coordinator import SyncCoordinator
from managers.rclone_service import RcloneServiceManager
from version import VERSION
import logging
import traceback

# Configuración de logging global para captura de fallos silenciosos
logging.basicConfig(
    filename=os.path.join(os.path.dirname(__file__), "crash.log"),
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sync Master")
    app.setStyleSheet("""
        QPushButton {
            background-color: #2D2D2D;
            color: #E0E0E0;
            border: 1px solid #4A4A4A;
            border-radius: 5px;
            padding: 6px 12px;
            font-size: 13px;
            text-align: center;
        }
        QPushButton:hover {
            background-color: #383838;
        }
        QPushButton:focus-visible {
            outline: none;
            border: 1px solid #9CDCFE;
        }
        QPushButton:pressed {
            background-color: #1E1E1E;
        }
    """)
    
    # Set global icon
    icon_path = os.path.join(os.path.dirname(__file__), "assets/logo.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    app.setQuitOnLastWindowClosed(False) # Keep app running when window closed
    
    # Initialize Shared Components
    config_manager = ConfigManager()
    coordinator = SyncCoordinator()
    
    # Initialize Managers with Coordinator
    onedrive_manager = OneDriveManager(config_manager, coordinator)
    gdrive_manager = GDriveManager(config_manager, coordinator)
    local_manager = LocalSyncManager(config_manager, coordinator)
    
    # Create System Tray
    tray = SystemTray()

    # Create Rclone Service Managers
    rclone_services = config_manager.get("rclone_services", []) or []
    rclone_managers = [RcloneServiceManager(config_manager, coordinator, s.get("name", "")) for s in rclone_services if s.get("name")]

    # Create main window
    window = MainWindow(config_manager, onedrive_manager, gdrive_manager, local_manager, VERSION, tray, rclone_managers)
    
    # Connect Tray Signals
    tray.show_window_requested.connect(window.show)
    tray.show_window_requested.connect(window.activateWindow)
    tray.quit_requested.connect(app.quit)
    
    def sync_all():
        # Sincronizar servicios estándar
        onedrive_manager.sync()
        gdrive_manager.sync()
        local_manager.sync()
        
        # Sincronizar servicios Rclone dinámicos
        for manager in rclone_managers:
            manager.sync()
        
    tray.sync_all_requested.connect(sync_all)

    # Start Timers (Auto-Sync)
    onedrive_manager.start_timer()
    gdrive_manager.start_timer()
    local_manager.start_timer()
    
    # Show window initially or start minimized
    if "--minimized" in sys.argv:
        print("Sync Master iniciado minimizado.")
        tray.show_message("Sync Master", "Iniciado en segundo plano.", QSystemTrayIcon.MessageIcon.Information)
    else:
        window.show()
    
    try:
        sys.exit(app.exec())
    except Exception as e:
        logging.critical(f"Fallo fatal en el bucle principal: {e}")
        logging.critical(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
