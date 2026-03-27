# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QPlainTextEdit, QFileDialog, QDialogButtonBox, QComboBox, QMessageBox
)
from PyQt6.QtCore import Qt, QProcess
import json
import subprocess


class RcloneServiceDialog(QDialog):
    def __init__(self, parent=None):
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
        )
        self.providers = self.load_providers()
        self.provider_descriptions = {p.get("Name"): p.get("Description", "") for p in self.providers}
        self.setup_ui()
        self.start_config()

    def setup_ui(self):
        main_layout = QVBoxLayout()

        form_layout = QVBoxLayout()

        name_row = QHBoxLayout()
        name_label = QLabel("Nombre del Servicio:")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Ej. MiDrive")
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

    def load_providers(self):
        try:
            output = subprocess.check_output(["rclone", "config", "providers"], text=True, timeout=8)
            data = json.loads(output)
            return sorted(data, key=lambda x: x.get("Name", ""))
        except Exception:
            return []

    def update_provider_desc(self, name):
        desc = self.provider_descriptions.get(name, "")
        self.provider_desc.setText(desc)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder:
            self.local_edit.setText(folder)

    def start_config(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            return

        self.config_completed = False
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)

        self.process = QProcess(self)
        self.process.setProgram("rclone")
        self.process.setArguments(["config"])
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.process_finished)
        self.process.start()
        self.terminal.appendPlainText(">>> Iniciando rclone config ...")

    def read_output(self):
        data = self.process.readAllStandardOutput().data().decode(errors="ignore")
        if data:
            self.terminal.appendPlainText(data.rstrip())
            self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

    def send_input(self):
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return
        text = self.input_line.text()
        if not text.endswith("\n"):
            text += "\n"
        self.process.write(text.encode())
        self.input_line.clear()

    def process_finished(self, exit_code, exit_status):
        self.config_completed = True
        self.terminal.appendPlainText(">>> rclone config finalizó.")
        self.button_box.button(QDialogButtonBox.StandardButton.Save).setEnabled(True)

    def accept(self):
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

        super().accept()

    def get_service(self):
        return {
            "name": self.name_edit.text().strip(),
            "provider": self.provider_combo.currentText().strip(),
            "local_dir": self.local_edit.text().strip()
        }

    def closeEvent(self, event):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
        super().closeEvent(event)

    def reject(self):
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
    def __init__(self, title, message, parent=None):
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

    def setup_ui(self, message):
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

    def start_config(self):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self.process = QProcess(self)
        self.process.setProgram("rclone")
        self.process.setArguments(["config"])
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.process_finished)
        self.process.start()
        self.terminal.appendPlainText(">>> Iniciando rclone config ...")

    def read_output(self):
        data = self.process.readAllStandardOutput().data().decode(errors="ignore")
        if data:
            self.terminal.appendPlainText(data.rstrip())
            self.terminal.verticalScrollBar().setValue(self.terminal.verticalScrollBar().maximum())

    def send_input(self):
        if not self.process or self.process.state() == QProcess.ProcessState.NotRunning:
            return
        text = self.input_line.text()
        if not text.endswith("\n"):
            text += "\n"
        self.process.write(text.encode())
        self.input_line.clear()

    def process_finished(self, exit_code, exit_status):
        self.terminal.appendPlainText(">>> rclone config finalizó.")

    def reject(self):
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

    def closeEvent(self, event):
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
        super().closeEvent(event)
