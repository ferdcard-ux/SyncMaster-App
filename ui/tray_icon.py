# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QObject, pyqtSignal
import os

class SystemTray(QObject):
    show_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    sync_all_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tray_icon = QSystemTrayIcon(parent)
        
        # Determine icon path
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets/logo.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(QIcon.fromTheme("folder-sync")) 
        
        self.setup_menu()
        self.tray_icon.show()
        
        self.tray_icon.activated.connect(self.on_activated)

    def setup_menu(self):
        menu = QMenu()
        
        show_action = menu.addAction("Mostrar App")
        show_action.triggered.connect(self.show_window_requested.emit)
        
        sync_action = menu.addAction("Sincronizar Todo")
        sync_action.triggered.connect(self.sync_all_requested.emit)
        
        menu.addSeparator()
        
        quit_action = menu.addAction("Salir")
        quit_action.triggered.connect(self.quit_requested.emit)
        
        self.tray_icon.setContextMenu(menu)

    def on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()

    def show_message(self, title, message, icon=QSystemTrayIcon.MessageIcon.Information):
        self.tray_icon.showMessage(title, message, icon)
