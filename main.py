
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

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sync Master")
    app.setStyleSheet("""
        QPushButton {
            background-color: #011403;
            color: #ffffff;
            border: 1px solid #0a2a10;
            border-radius: 4px;
            padding: 6px 12px;
            text-align: center;
        }
        QPushButton:hover {
            background-color: #03380c;
        }
        QPushButton:focus {
            outline: none;
            border: 2px solid #2f7a3a;
        }
        QPushButton:pressed {
            background-color: #001c06;
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
        onedrive_manager.sync()
        gdrive_manager.sync()
        local_manager.sync()
        
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
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
