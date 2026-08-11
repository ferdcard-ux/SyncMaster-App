from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class LogDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the log dialog with a service list and stacked editor panel."""
        super().__init__(parent)
        self.setWindowTitle("Registro de Sync Master")
        self.resize(900, 560)

        self.service_list: QListWidget = QListWidget()
        self.service_list.setMinimumWidth(220)
        self.service_list.currentRowChanged.connect(self._on_service_selected)
        self.stack: QStackedWidget = QStackedWidget()

        layout = QHBoxLayout(self)
        layout.addWidget(self.service_list)
        layout.addWidget(self.stack, 1)

        self._editors: dict[str, QTextEdit] = {}
        self._containers: dict[str, QWidget] = {}
        self._has_logs: dict[str, bool] = {}
        self._order: list[str] = []

        self.setStyleSheet(
            "QListWidget { background-color: #181818; border: 1px solid #2D2D2D; }"
            "QListWidget::item { padding: 8px; color: #E0E0E0; }"
            "QListWidget::item:selected { background-color: #3C3C3C; border-left: 3px solid #4CAF50; }"
            "QTextEdit { background-color: #1E1E1E; color: #E0E0E0; font-family: 'Fira Code', 'Courier New'; }"
        )

    def append_log(self, service: str, message: str) -> None:
        """Append a log message to the specified service's editor.

        Args:
            service: Service name to route the log entry to.
            message: Log text to append.
        """
        editor = self._ensure_editor(service)
        if not self._has_logs.get(service):
            editor.clear()
            self._has_logs[service] = True
        editor.append(message)
        scrollbar = editor.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _ensure_editor(self, service: str) -> QTextEdit:
        if service not in self._editors:
            container = QWidget()
            vbox = QVBoxLayout(container)

            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            text_edit.setPlainText("Sin registros")
            self._has_logs[service] = False
            vbox.addWidget(text_edit)

            btn_row = QHBoxLayout()
            clear_btn = QPushButton("Limpiar Registro")
            clear_btn.setStyleSheet(
                "QPushButton{background:#2D2D2D;color:#E0E0E0;border:1px solid #3C3C3C;border-radius:4px;padding:4px 12px;}"
                "QPushButton:hover{border-color:#4CAF50;}"
            )
            clear_btn.clicked.connect(lambda _, s=service: self.clear_service_log(s))

            export_btn = QPushButton("Exportar Registro")
            export_btn.setStyleSheet(
                "QPushButton{background:#2D2D2D;color:#E0E0E0;border:1px solid #3C3C3C;border-radius:4px;padding:4px 12px;}"
                "QPushButton:hover{border-color:#4CAF50;}"
            )
            export_btn.clicked.connect(lambda _, s=service: self.export_service_log(s))

            btn_row.addWidget(clear_btn)
            btn_row.addWidget(export_btn)
            btn_row.addStretch()
            vbox.addLayout(btn_row)

            self._editors[service] = text_edit
            self._containers[service] = container
            self._order.append(service)
            self.stack.addWidget(container)

            item = QListWidgetItem(service)
            item.setData(Qt.ItemDataRole.UserRole, service)
            self.service_list.addItem(item)
            if self.service_list.count() == 1:
                self.service_list.setCurrentRow(0)

        return self._editors[service]

    def _on_service_selected(self, row: int) -> None:
        if row >= 0:
            self.stack.setCurrentIndex(row)

    def clear_logs(self) -> None:
        """Clear all log entries from every service editor."""
        for editor in self._editors.values():
            editor.clear()
            editor.setPlainText("Sin registros")
        for service in self._has_logs:
            self._has_logs[service] = False

    def clear_service_log(self, service: str) -> None:
        """Clear the log entries for a single service.

        Args:
            service: Service name whose log should be cleared.
        """
        editor = self._editors.get(service)
        if editor:
            editor.clear()
            editor.setPlainText("Sin registros")
            self._has_logs[service] = False

    def export_service_log(self, service: str) -> None:
        """Export a service's log to a text file via a save dialog.

        Args:
            service: Service name whose log will be exported.
        """
        editor = self._editors.get(service)
        if not editor:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Exportar {service}",
            f"{service}_log.txt",
            "Text Files (*.txt)",
        )
        if not path:
            return
        content = editor.toPlainText().strip()
        if not self._has_logs.get(service) or not content or content == "Sin registros":
            return
        try:
            with open(path, "w", encoding="utf-8") as file_handle:
                file_handle.write(content)
        except Exception:
            pass
