# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

from __future__ import annotations

import json
import subprocess
from typing import Any

from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.paths import get_rclone_binary


class RcloneServiceDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, provider_hint: str | None = None, name_hint: str | None = None) -> None:
        """Initialize the Rclone service creation dialog.

        Args:
            parent: Parent widget.
            provider_hint: Pre-selected cloud provider backend name.
            name_hint: Pre-filled service name.
        """
        super().__init__(parent)
        self.setWindowTitle("Añadir Servicio Rclone")
        self.resize(700, 520)
        self.process = None
        self.config_completed = False
        self.setStyleSheet(
            "QWidget { background-color: #1E1E1E; color: #E0E0E0; font-size: 13px; }"
            "QPushButton { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #4A4A4A; border-radius: 5px; padding: 6px 12px; text-align: center; }"
            "QPushButton:hover { background-color: #383838; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #9CDCFE; }"
            "QPushButton:pressed { background-color: #1E1E1E; }"
            "QLabel { color: #E0E0E0; }"
            "QLineEdit, QPlainTextEdit { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #3C3C3C; border-radius: 4px; }"
            "QToolTip { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #4CAF50; padding: 4px; font-size: 12px; }"
        )
        self.providers = self.load_providers()
        self.provider_descriptions = {p.get("Name"): p.get("Description", "") for p in self.providers}
        self._auto_named = False
        self.setup_ui()
        if provider_hint:
            idx = self.provider_combo.findText(provider_hint)
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
            else:
                self.provider_combo.setCurrentText(provider_hint)
        if name_hint:
            self.name_edit.setText(name_hint)
        self.start_config()

    def setup_ui(self) -> None:
        """Build the form fields, interactive terminal, and action buttons."""
        main_layout = QVBoxLayout()

        form_layout = QVBoxLayout()

        name_row = QHBoxLayout()
        name_label = QLabel("Nombre del Servicio:")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ej. MiDrive")
        self.name_edit.textChanged.connect(self._on_name_edited)
        name_row.addWidget(name_label)
        name_row.addWidget(self.name_edit)
        form_layout.addLayout(name_row)

        provider_row = QHBoxLayout()
        provider_label = QLabel("Proveedor (backend):")
        self.provider_combo = QComboBox()
        self.provider_combo.setEditable(True)
        self.provider_combo.setMinimumWidth(220)
        self.provider_combo.addItems([p.get("Name", "") for p in self.providers])
        if not self.providers:
            self.provider_combo.addItem("drive")
        self.provider_combo.currentTextChanged.connect(self.update_provider_desc)
        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.provider_combo)
        form_layout.addLayout(provider_row)

        self.provider_desc = QLabel("")
        self.provider_desc.setWordWrap(True)
        self.provider_desc.setStyleSheet("color: #555; font-size: 11px;")
        form_layout.addWidget(self.provider_desc)
        self.update_provider_desc(self.provider_combo.currentText())

        local_row = QHBoxLayout()
        local_label = QLabel("Directorio Local:")
        self.local_edit = QLineEdit()
        self.local_edit.setPlaceholderText("/ruta/local")
        browse_btn = QPushButton("Explorar")
        browse_btn.clicked.connect(self.browse_folder)
        local_row.addWidget(local_label)
        local_row.addWidget(self.local_edit)
        local_row.addWidget(browse_btn)
        form_layout.addLayout(local_row)

        main_layout.addLayout(form_layout)

        hint = QLabel("Terminal interactiva: completa aquí el proceso de `rclone config`.")
        hint.setStyleSheet("font-weight: bold; margin-top: 8px;")
        main_layout.addWidget(hint)

        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet(
            "background-color: #1E1E1E; color: #E0E0E0; font-family: 'Fira Code', 'Courier New', monospace; font-size: 13px; border: 1px solid #3C3C3C; border-radius: 6px;"
        )
        main_layout.addWidget(self.terminal)

        input_row = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Escribe una respuesta y presiona Enter")
        self.input_line.returnPressed.connect(self.send_input)
        send_btn = QPushButton("Enviar")
        send_btn.clicked.connect(self.send_input)
        self.start_btn = QPushButton("Reiniciar rclone config")
        self.start_btn.clicked.connect(self.start_config)
        input_row.addWidget(self.input_line)
        input_row.addWidget(send_btn)
        input_row.addWidget(self.start_btn)
        main_layout.addLayout(input_row)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)

    def load_providers(self) -> list[dict[str, Any]]:
        """Retrieve available rclone backend providers.

        Returns:
            List of provider dicts with 'Name' and 'Description' keys.
        """
        try:
            output = subprocess.check_output([get_rclone_binary(), "config", "providers"], text=True, timeout=8)
            data = json.loads(output)
            return sorted(data, key=lambda x: x.get("Name", ""))
        except Exception:
            return []

    @staticmethod
    def _suggest_name(provider: str) -> str:
        known = {
            "drive": "GoogleDrive",
            "onedrive": "OneDrive",
            "mega": "Mega",
            "dropbox": "Dropbox",
            "s3": "S3",
            "swift": "Swift",
            "b2": "B2",
            "box": "Box",
            "pcloud": "pCloud",
            "yandex": "Yandex",
            "nextcloud": "Nextcloud",
            "webdav": "WebDAV",
            "sftp": "SFTP",
            "ftp": "FTP",
            "smb": "SMB",
            "local": "Local",
        }
        if provider in known:
            return known[provider]
        return provider.replace("_", " ").title().replace(" ", "")

    def _on_name_edited(self, text: str) -> None:
        if getattr(self, '_setting_name', False):
            return
        self._auto_named = False

    def update_provider_desc(self, name: str) -> None:
        """Update the provider description label and auto-suggest a service name.

        Args:
            name: Provider backend name selected by the user.
        """
        desc = self.provider_descriptions.get(name, "")
        self.provider_desc.setText(desc)
        suggested = self._suggest_name(name)
        current_name = self.name_edit.text().strip()
        if not current_name or self._auto_named:
            self._setting_name = True
            self.name_edit.setText(suggested)
            self._setting_name = False
            self._auto_named = True

    def browse_folder(self) -> None:
        """Open a folder selection dialog and populate the local directory field."""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder:
            self.local_edit.setText(folder)

    def start_config(self) -> None:
        """Launch the interactive rclone config process in the embedded terminal."""
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            return

        self.config_completed = False
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

        rclone_bin = get_rclone_binary()
        self.process = QProcess(self)
        self.process.setProgram(rclone_bin)
        self.process.setArguments(["config"])
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.process_finished)
        self.process.start()
        self.terminal.appendPlainText(">>> Iniciando rclone config ...")

    def read_output(self) -> None:
        """Read and display stdout/stderr from the rclone config process."""
        data = self.process.readAllStandardOutput().data().decode(errors="ignore")
        if data:
            self.terminal.appendPlainText(data.rstrip())
            self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

    def send_input(self) -> None:
        """Send user-typed text to the rclone config process stdin."""
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return
        text = self.input_line.text()
        if not text.endswith("\n"):
            text += "\n"
        self.process.write(text.encode())
        self.input_line.clear()

    def process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """Handle rclone config process completion."""
        self.config_completed = True
        self.terminal.appendPlainText(">>> rclone config finalizó.")
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)

    def accept(self) -> None:
        """Validate inputs and close the dialog, terminating any running process."""
        if not self.config_completed:
            QMessageBox.warning(self, "Configuración en curso", "Finaliza primero el proceso de rclone config antes de guardar.")
            return

        name = self.name_edit.text().strip()
        provider = self.provider_combo.currentText().strip()
        local_dir = self.local_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "Campo requerido", "Debes ingresar un nombre de servicio.")
            return
        if not provider:
            QMessageBox.warning(self, "Campo requerido", "Debes seleccionar o escribir un proveedor.")
            return
        if not local_dir:
            QMessageBox.warning(self, "Campo requerido", "Debes seleccionar un directorio local.")
            return

        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.process.kill()
        super().accept()

    def get_service(self) -> dict[str, str]:
        """Return the configured service details.

        Returns:
            Dict with 'name', 'provider', and 'local_dir' keys.
        """
        return {
            "name": self.name_edit.text().strip(),
            "provider": self.provider_combo.currentText().strip(),
            "local_dir": self.local_edit.text().strip()
        }

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
        super().closeEvent(event)

    def reject(self) -> None:
        """Cancel the dialog, terminating any running rclone config process."""
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            answer = QMessageBox.question(
                self,
                "Cerrar terminal",
                "El proceso de rclone config sigue activo. ¿Deseas cerrarlo y cancelar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.process.terminate()
        super().reject()


class RcloneConfigTerminalDialog(QDialog):
    def __init__(self, title: str, message: str, parent: QWidget | None = None) -> None:
        """Initialize a standalone rclone config terminal dialog.

        Args:
            title: Window title.
            message: Instructional message shown above the terminal.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 460)
        self.process = None
        self.setStyleSheet(
            "QPushButton { background-color: #011403; color: #ffffff; border: 1px solid #0a2a10; border-radius: 4px; padding: 6px 12px; text-align: center; }"
            "QPushButton:hover { background-color: #03380c; }"
            "QPushButton:focus { outline: none; border: 2px solid #2f7a3a; }"
            "QPushButton:pressed { background-color: #001c06; }"
        )
        self.setup_ui(message)
        self.start_config()

    def setup_ui(self, message: str) -> None:
        """Build the terminal display, input row, and close button.

        Args:
            message: Instructional text displayed above the terminal.
        """
        main_layout = QVBoxLayout()

        info = QLabel(message)
        info.setWordWrap(True)
        info.setStyleSheet("font-weight: bold; margin-bottom: 6px;")
        main_layout.addWidget(info)

        self.terminal = QPlainTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setStyleSheet(
            "background-color: #111; color: #e6e6e6; font-family: 'Fira Code', 'Courier New', monospace; font-size: 11px;"
        )
        main_layout.addWidget(self.terminal)

        input_row = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Escribe una respuesta y presiona Enter")
        self.input_line.returnPressed.connect(self.send_input)
        send_btn = QPushButton("Enviar")
        send_btn.clicked.connect(self.send_input)
        input_row.addWidget(self.input_line)
        input_row.addWidget(send_btn)
        main_layout.addLayout(input_row)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        self.button_box.accepted.connect(self.accept)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)

    def start_config(self) -> None:
        """Launch the interactive rclone config process."""
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            return
        rclone_bin = get_rclone_binary()
        self.process = QProcess(self)
        self.process.setProgram(rclone_bin)
        self.process.setArguments(["config"])
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.process_finished)
        self.process.start()
        self.terminal.appendPlainText(">>> Iniciando rclone config ...")

    def read_output(self) -> None:
        """Read and display stdout/stderr from the rclone config process."""
        data = self.process.readAllStandardOutput().data().decode(errors="ignore")
        if data:
            self.terminal.appendPlainText(data.rstrip())
            self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

    def send_input(self) -> None:
        """Send user-typed text to the rclone config process stdin."""
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return
        text = self.input_line.text()
        if not text.endswith("\n"):
            text += "\n"
        self.process.write(text.encode())
        self.input_line.clear()

    def process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        """Handle rclone config process completion."""
        self.terminal.appendPlainText(">>> rclone config finalizó.")

    def reject(self) -> None:
        """Cancel the dialog, terminating any running rclone config process."""
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            answer = QMessageBox.question(
                self,
                "Cerrar terminal",
                "El proceso de rclone config sigue activo. ¿Deseas cerrarlo?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.process.terminate()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
        super().closeEvent(event)
