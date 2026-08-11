# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.rclone_client import (
    apply_client_id,
    list_remotes,
    remote_backend,
    supports_custom_client_id,
)
from ui.rclone_service_dialog import RcloneConfigTerminalDialog


class ClientIdAssistantDialog(QDialog):
    """Assistant to configure a user's own Client ID and re-authorize a remote."""

    def __init__(self, parent: QWidget | None = None, preset_remote: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Asistente: Tu propio Client ID")
        self.setMinimumSize(560, 380)
        self.setStyleSheet(
            "QWidget { background-color: #1E1E1E; color: #E0E0E0; font-size: 13px; }"
            "QLabel { color: #E0E0E0; }"
            "QPushButton { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #3C3C3C; border-radius: 5px; padding: 6px 12px; text-align: center; }"
            "QPushButton:hover { background-color: #383838; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
            "QLineEdit, QComboBox { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #3C3C3C; border-radius: 4px; padding: 4px; }"
        )

        self.preset_remote = preset_remote
        self.setup_ui()
        self.refresh_remotes()

    def setup_ui(self) -> None:
        """Build the assistant form."""
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        intro = QLabel(
            "¿Por qué conviene usar tu propio Client ID?\n\n"
            "rclone incluye un Client ID público que comparten miles de personas, "
            "así que Google/Microsoft pueden limitar su uso cuando hay mucha demanda.\n"
            "Con tu propio Client ID tienes tu propia cuota y evitas la mayoría de errores "
            "de saturación (Error 403 / Rate Limit).\n\n"
            "Paso 1: Crea el Client ID en el panel de desarrolladores del proveedor.\n"
            "  • Google Drive: console.cloud.google.com → Credenciales → ID de cliente OAuth\n"
            "  • OneDrive: portal.azure.com → Registros de aplicaciones → Credenciales\n"
            "Paso 2: Pega aquí tu Client ID (y Client Secret, si el proveedor lo pide).\n"
            "Paso 3: Haz clic en 'Aplicar y Reconectar' para volver a autorizar la cuenta."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #C7C7C7; font-size: 12px;")
        root.addWidget(intro)

        remote_row = QHBoxLayout()
        remote_row.addWidget(QLabel("Cuenta rclone:"))
        self.remote_combo = QComboBox()
        self.remote_combo.setEditable(True)
        self.remote_combo.currentTextChanged.connect(self._on_remote_changed)
        remote_row.addWidget(self.remote_combo, 1)
        refresh_btn = QPushButton("Actualizar")
        refresh_btn.clicked.connect(self.refresh_remotes)
        remote_row.addWidget(refresh_btn)
        root.addLayout(remote_row)

        self.backend_label = QLabel("")
        self.backend_label.setStyleSheet("color: #888888; font-size: 12px;")
        root.addWidget(self.backend_label)

        id_row = QHBoxLayout()
        id_row.addWidget(QLabel("Client ID:"))
        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText("1234567890-xxxxxxxx.apps.googleusercontent.com")
        id_row.addWidget(self.client_id_edit, 1)
        root.addLayout(id_row)

        secret_row = QHBoxLayout()
        secret_row.addWidget(QLabel("Client Secret:"))
        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setPlaceholderText("Opcional en algunos proveedores")
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        secret_row.addWidget(self.client_secret_edit, 1)
        root.addLayout(secret_row)

        self.apply_btn = QPushButton("Aplicar Client ID y Reconectar")
        self.apply_btn.setStyleSheet(
            "QPushButton { background-color: #2d7a33; color: #ffffff; border: 1px solid #256026; border-radius: 5px; padding: 8px 14px; }"
            "QPushButton:hover { background-color: #3a9c4b; border-color: #4CAF50; }"
        )
        self.apply_btn.clicked.connect(self.apply_and_reconnect)
        root.addWidget(self.apply_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.reject)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def refresh_remotes(self) -> None:
        """Reload the list of rclone remotes into the combo box."""
        current = self.remote_combo.currentText().strip()
        self.remote_combo.clear()
        self.remote_combo.addItems(list_remotes() or [])
        if self.preset_remote and self.preset_remote not in [self.remote_combo.itemText(i) for i in range(self.remote_combo.count())]:
            self.remote_combo.addItem(self.preset_remote)
        if self.preset_remote:
            self.remote_combo.setCurrentText(self.preset_remote)
        elif current:
            self.remote_combo.setCurrentText(current)
        self._on_remote_changed(self.remote_combo.currentText())

    def _on_remote_changed(self, remote: str) -> None:
        remote = remote.strip()
        if not remote:
            self.backend_label.setText("")
            self.apply_btn.setEnabled(False)
            return
        supported, explanation = supports_custom_client_id(remote)
        backend = remote_backend(remote)
        self.backend_label.setText(f"Proveedor: {backend or 'desconocido'} — {explanation}")
        self.apply_btn.setEnabled(supported)

    def apply_and_reconnect(self) -> None:
        """Apply the Client ID and open the interactive reconnect terminal."""
        remote = self.remote_combo.currentText().strip()
        client_id = self.client_id_edit.text().strip()
        client_secret = self.client_secret_edit.text().strip()

        if not remote:
            QMessageBox.warning(self, "Falta la cuenta", "Selecciona la cuenta rclone a actualizar.")
            return
        if not client_id:
            QMessageBox.warning(self, "Falta el Client ID", "Pega tu Client ID antes de continuar.")
            return

        ok, message = apply_client_id(remote, client_id, client_secret)
        if not ok:
            QMessageBox.critical(self, "Error", f"No se pudo aplicar el Client ID:\n\n{message}")
            return

        QMessageBox.information(
            self,
            "Client ID aplicado",
            f"{message}\n\nA continuación se abrirá la terminal interactiva de rclone "
            "para que autorices la cuenta de nuevo (elige el remoto y sigue el flujo de conexión).",
        )

        terminal = RcloneConfigTerminalDialog(
            "Reconectar cuenta rclone",
            f"Terminal interactiva de rclone para reconectar '{remote}'.\n"
            "Sigue el flujo de rclone config (opción 'n' de crear remoto nuevo, "
            "o usa 'config reconnect' si tu versión lo soporta).",
            self,
        )
        terminal.exec()
        self.accept()

    @staticmethod
    def create_callback(parent: QWidget | None = None, remote: str | None = None) -> Callable[[], None]:
        """Build a callback that opens the assistant dialog."""
        def _open() -> None:
            dialog = ClientIdAssistantDialog(parent, preset_remote=remote)
            dialog.exec()
        return _open
