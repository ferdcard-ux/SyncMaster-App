# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

# Sync Master main entry point.
# Copyright 2026 FerDev

import glob
import logging
import os
import sys
import threading
import traceback
from datetime import datetime

from PyQt6.QtCore import QtMsgType, qInstallMessageHandler
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

# --- LOGGING ULTRA-ROBUSTO ---
from core.paths import get_logs_dir
from managers.config import ConfigManager
from managers.coordinator import SyncCoordinator
from managers.gdrive import GDriveManager
from managers.local_sync import LocalSyncManager
from managers.onedrive import OneDriveManager
from managers.rclone_service import RcloneServiceManager
from ui.main_window import MainWindow
from ui.tray_icon import SystemTray
from version import VERSION

LOGS_DIR = get_logs_dir()
os.makedirs(LOGS_DIR, exist_ok=True)

def _daily_log_path():
    date_token = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOGS_DIR, f"syncmaster-{date_token}.log")

def _cleanup_old_logs(keep=3):
    pattern = os.path.join(LOGS_DIR, "*.log")
    existing = sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True)
    for old in existing[keep:]:
        try:
            os.remove(old)
        except OSError:
            pass

_cleanup_old_logs()
CRASH_LOG = _daily_log_path()

# Redirección de flujos básicos para capturar errores de C++/Qt o prints perdidos
class LoggerWriter:
    def __init__(self, filename):
        self.file = open(filename, 'a', buffering=1, encoding='utf-8')
    def write(self, message):
        self.file.write(message)
        self.file.flush()
    def flush(self):
        self.file.flush()

sys.stdout = LoggerWriter(CRASH_LOG)
sys.stderr = sys.stdout

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(CRASH_LOG, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

def _threading_excepthook(args):
    logging.critical(
        f"UNHANDLED THREAD EXCEPTION ({args.thread.name}):",
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )

threading.excepthook = _threading_excepthook

def _qt_message_handler(mode, context, message):
    severity = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }.get(mode, logging.INFO)
    source = f"{context.file or 'qt'}:{context.line}"
    logging.log(severity, f"QT ({source}) [{context.category}] {message}")

qInstallMessageHandler(_qt_message_handler)

def exception_hook(exctype, value, tb):
    """Captura de excepciones a nivel global (Python)."""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    logging.critical(f"CRASH DETECTADO (sys.excepthook):\n{error_msg}")
    sys.exit(1)

sys.excepthook = exception_hook

def show_dependency_error(missing_deps):
    from PyQt6.QtWidgets import QMessageBox
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Dependencias faltantes")
    msg.setText("SyncMaster no puede iniciar porque faltan los siguientes componentes:")
    msg.setInformativeText("\n\n".join(missing_deps))
    msg.setDetailedText(
        "rclone es el motor de sincronización que utiliza SyncMaster para todos los servicios "
        "(Google Drive, OneDrive, sincronización local, etc.). Sin él la aplicación no puede funcionar.\n\n"
        "Puedes descargarlo desde: https://rclone.org/downloads/\n"
        "Instálalo y asegúrate de que 'rclone' esté accesible desde el PATH del sistema."
    )
    msg.exec()


def main():
    logging.info(f"--- Iniciando SyncMaster v{VERSION} ---")
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("Sync Master")

        # Verificar dependencias antes de continuar
        from core.dependency_check import check_dependencies
        missing = check_dependencies()
        if missing:
            show_dependency_error(missing)
            logging.critical("Dependencias faltantes detectadas. Abortando.")
            sys.exit(1)

        # Estilo Global
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
            QPushButton:hover { background-color: #383838; }
            QPushButton:focus-visible { outline: none; border: 1px solid #9CDCFE; }
            QPushButton:pressed { background-color: #1E1E1E; }
        """)

        # Icono Global
        icon_path = os.path.join(os.path.dirname(__file__), "assets/logo.png")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        app.setQuitOnLastWindowClosed(False)

        # Componentes Core
        config_manager = ConfigManager()
        coordinator = SyncCoordinator()

        # Managers
        onedrive_manager = OneDriveManager(config_manager, coordinator)
        gdrive_manager = GDriveManager(config_manager, coordinator)
        local_manager = LocalSyncManager(config_manager, coordinator)

        # System Tray
        tray = SystemTray()

        # Rclone dynamic services
        rclone_services = config_manager.get("rclone_services", []) or []
        rclone_managers = [RcloneServiceManager(config_manager, coordinator, s.get("name", "")) for s in rclone_services if s.get("name")]

        # Main Window
        window = MainWindow(config_manager, onedrive_manager, gdrive_manager, local_manager, VERSION, tray, rclone_managers)

        def shutdown_all():
            logging.info("Iniciando cierre ordenado de managers...")
            try:
                window.shutdown_all_managers()
            except Exception:
                logging.exception("Error durante el cierre ordenado de managers")

        # Conexiones Tray
        tray.show_window_requested.connect(window.show)
        tray.show_window_requested.connect(window.activateWindow)
        tray.quit_requested.connect(app.quit)
        app.aboutToQuit.connect(shutdown_all)

        def sync_all():
            logging.info("Sincronización manual solicitada desde el tray.")
            window.sync_all_managers()

        tray.sync_all_requested.connect(sync_all)

        # Timers
        onedrive_manager.start_timer()
        gdrive_manager.start_timer()
        local_manager.start_timer()

        if "--minimized" in sys.argv:
            logging.info("Iniciando en modo minimizado.")
            tray.show_message("Sync Master", "Iniciado en segundo plano.", QSystemTrayIcon.MessageIcon.Information)
        else:
            window.show()

        logging.info("Entrando en el bucle de eventos de Qt.")
        exit_code = app.exec()
        logging.info(f"Aplicación cerrada normalmente con código {exit_code}")
        sys.exit(exit_code)

    except Exception:
        error_msg = traceback.format_exc()
        logging.critical(f"FALLO FATAL DURANTE LA EJECUCIÓN:\n{error_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()
