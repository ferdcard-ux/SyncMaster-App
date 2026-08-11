# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.
from __future__ import annotations

import os

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon


class SystemTray(QObject):
    show_window_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    sync_all_requested = pyqtSignal()

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the system tray icon with menu and icon."""
        super().__init__(parent)
        self.tray_icon: QSystemTrayIcon = QSystemTrayIcon(parent)

        # Determine icon path
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets/logo.png")
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            self.tray_icon.setIcon(QIcon.fromTheme("folder-sync"))

        self.setup_menu()
        self.tray_icon.show()

        self.tray_icon.activated.connect(self.on_activated)

    def setup_menu(self) -> None:
        """Build and attach the context menu to the tray icon."""
        menu = QMenu()

        show_action = menu.addAction("Mostrar App")
        show_action.triggered.connect(self.show_window_requested.emit)

        sync_action = menu.addAction("Sincronizar Todo")
        sync_action.triggered.connect(self.sync_all_requested.emit)

        menu.addSeparator()

        quit_action = menu.addAction("Salir")
        quit_action.triggered.connect(self.quit_requested.emit)

        self.tray_icon.setContextMenu(menu)

    def on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation events.

        Args:
            reason: The type of user interaction that activated the icon.
        """
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window_requested.emit()

    def show_message(self, title: str, message: str, icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information) -> None:
        """Display a system tray notification bubble.

        Args:
            title: Notification title.
            message: Notification body text.
            icon: Icon type for the notification.
        """
        self.tray_icon.showMessage(title, message, icon)
