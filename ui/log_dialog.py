from PyQt6.QtWidgets import QDialog, QTabWidget, QVBoxLayout, QTextEdit, QWidget, QPushButton, QHBoxLayout, QFileDialog

class LogDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registro de Sync Master")
        self.resize(700, 500)
        self.tabs = QTabWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self._editors = {}
        self._containers = {}
        self._has_logs = {}
        self.tabs.setStyleSheet(
            "QTabBar::tab { background: #2D2D2D; color: #E0E0E0; padding: 8px 16px; border: 1px solid #2D2D2D; }"
            "QTabBar::tab:selected { background: #3C3C3C; border: 1px solid #4CAF50; }"
            "QTabBar::tab:hover { border: 1px solid #4CAF50; }"
            "QTabBar::tab:focus { border: 1px solid #4CAF50; }"
        )

    def append_log(self, service, message):
        editor = self._ensure_editor(service)
        if not self._has_logs.get(service):
            editor.clear()
            self._has_logs[service] = True
        editor.append(message)
        scrollbar = editor.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _ensure_editor(self, service):
        if service not in self._editors:
            container = QWidget()
            vbox = QVBoxLayout()
            container.setLayout(vbox)
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setStyleSheet(
                "QTextEdit { background-color: #1E1E1E; color: #E0E0E0; font-family: 'Fira Code', 'Courier New'; }"
            )
            text_edit.setPlainText("Sin registros")
            self._has_logs[service] = False
            vbox.addWidget(text_edit)
            btn_row = QHBoxLayout()
            clear_btn = QPushButton("Limpiar Registro")
            clear_btn.setStyleSheet("QPushButton{background:#2D2D2D;color:#E0E0E0;border:1px solid #3C3C3C;border-radius:4px;padding:4px 12px;}QPushButton:hover{border-color:#4CAF50;}")
            clear_btn.clicked.connect(lambda _, s=service: self.clear_service_log(s))
            export_btn = QPushButton("Exportar Registro")
            export_btn.setStyleSheet("QPushButton{background:#2D2D2D;color:#E0E0E0;border:1px solid #3C3C3C;border-radius:4px;padding:4px 12px;}QPushButton:hover{border-color:#4CAF50;}")
            export_btn.clicked.connect(lambda _, s=service: self.export_service_log(s))
            btn_row.addWidget(clear_btn)
            btn_row.addWidget(export_btn)
            vbox.addLayout(btn_row)
            self._editors[service] = text_edit
            self._containers[service] = container
            self.tabs.addTab(container, service)
        return self._editors[service]

    def clear_logs(self):
        for editor in self._editors.values():
            editor.clear()
            editor.setPlainText("Sin registros")
        for service in self._has_logs:
            self._has_logs[service] = False

    def clear_service_log(self, service):
        editor = self._editors.get(service)
        if editor:
            editor.clear()
            editor.setPlainText("Sin registros")
            self._has_logs[service] = False

    def export_service_log(self, service):
        editor = self._editors.get(service)
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(self, f"Exportar {service}", f"{service}_log.txt", "Text Files (*.txt)")
        if not path:
            return
        content = editor.toPlainText().strip()
        if not self._has_logs.get(service) or not content or content == "Sin registros":
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception:
            pass
