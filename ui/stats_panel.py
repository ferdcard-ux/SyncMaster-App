# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# Traducción de estados técnicos a lenguaje cotidiano.
STATUS_IN_PLAIN_LANGUAGE: dict[str, str] = {
    "Activo": "Todo en orden: la sincronización automática está funcionando.",
    "Desactivado": "Este servicio está apagado y no se sincroniza por ahora.",
    "Sincronizando": "Está copiando archivos en este momento.",
    "Escaneando": "Está revisando qué archivos cambiaron antes de copiar.",
    "En Espera": "Está en fila: otra sincronización está usando la misma carpeta.",
    "Sin Conexión": "No hay internet. Volverá a intentarlo automáticamente.",
    "Error Config": "Falta configurar algo: revisa las rutas o el proveedor.",
    "Limitado (API)": "El servicio en la nube pidió calma: se espera unos minutos antes de reintentar.",
    "Ritmo reducido": "La nube está saturada: se copian menos archivos a la vez para no fallar.",
    "Error": "Algo salió mal. Revisa los registros detallados.",
    "Advertencia": "Ocurrió un detalle menor, pero la sincronización sigue adelante.",
    "Detenido": "La sincronización se detuvo por completo.",
    "Sincronizado": "Terminó de copiar todo correctamente.",
}

STATUS_COLORS: dict[str, str] = {
    "Activo": "#28a745",
    "Sincronizado": "#28a745",
    "Desactivado": "#888888",
    "Sincronizando": "#4CAF50",
    "Escaneando": "#4CAF50",
    "En Espera": "#FF9800",
    "Sin Conexión": "#FF9800",
    "Ritmo reducido": "#FF9800",
    "Limitado (API)": "#F44336",
    "Error Config": "#F44336",
    "Error": "#F44336",
    "Advertencia": "#FF9800",
    "Detenido": "#888888",
}


def status_in_plain_language(status: str) -> str:
    """Return a plain-language explanation for a technical status string.

    Args:
        status: Raw status string emitted by a service manager.

    Returns:
        A friendly explanation, or the raw status if unknown.
    """
    return STATUS_IN_PLAIN_LANGUAGE.get(status, f"Estado: {status}")


class StatsCounterButton(QFrame):
    """Clickable counter that opens the detail dialog on activation.

    Se implementa como QFrame clicable (no QPushButton) para evitar que el
    botón pinte su propio texto y se superponga con los QLabel internos, o que
    el padding del estilo recorte el número grande.

    Attributes:
        counter_key: Key identifying the counter (completed, warnings, critical).
        on_click: Callable invoked when the button is pressed.
    """

    clicked = pyqtSignal()

    def __init__(self, title: str, value: str, counter_key: str, on_click: Callable[[], None]) -> None:
        super().__init__()
        self.counter_key = counter_key
        self._on_click = on_click
        self._color = "#E0E0E0"

        self.setObjectName("statsCounterFrame")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Clic para ver el detalle de este conteo")
        self.setStyleSheet(
            "QFrame#statsCounterFrame { background-color: #2D2D2D; border: 1px solid #3C3C3C;"
            " border-radius: 8px; }"
            "QFrame#statsCounterFrame:hover { background-color: #383838; border-color: #4CAF50; }"
            "QFrame#statsCounterFrame:pressed { background-color: #1E1E1E; }"
        )

        self.value_label = QLabel(value)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet(
            f"color: {self._color}; font-size: 20px; font-weight: 600; background: transparent; border: none;"
        )
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            "color: #B5B5B5; font-size: 11px; background: transparent; border: none;"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)
        self.setLayout(layout)

        self.clicked.connect(self._on_click)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def set_value(self, value: int) -> None:
        """Update the displayed count.

        Args:
            value: New count to display.
        """
        self.value_label.setText(str(value))

    def set_color(self, color: str) -> None:
        """Set the color of the counter number.

        Args:
            color: CSS color string.
        """
        self._color = color
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 20px; font-weight: 600; background: transparent; border: none;"
        )


class StatsDetailDialog(QDialog):
    """Dialog showing per-service detail for a single counter in plain language.

    Cuando ``counter_key`` es una categoría conocida, solo se muestran los
    eventos de esa categoría (con nombres de archivo para "completed"). Con un
    valor vacío se muestran todas las categorías con sus contadores.
    """

    def __init__(self, title: str, counts_by_service: dict[str, Any],
                 display_names: dict[str, str], parent: QWidget | None = None,
                 counter_key: str = "") -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(480, 360)
        self.setStyleSheet(
            "QDialog { background-color: #1E1E1E; }"
            "QLabel { color: #E0E0E0; }"
            "QPushButton { background-color: #2D2D2D; color: #E0E0E0;"
            " border: 1px solid #3C3C3C; border-radius: 5px; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #383838; border-color: #4CAF50; }"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        subtitle = QLabel(
            "Haz clic en un contador para ver, por servicio, qué generó cada número."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #B5B5B5; font-size: 12px;")
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(8)

        service_keys = sorted(counts_by_service.keys(), key=lambda k: display_names.get(k, k).lower())
        self._add_service_rows(body_layout, counts_by_service, display_names, service_keys, counter_key)

        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_btn)
        root.addLayout(close_row)

    @staticmethod
    def _add_service_rows(layout: QVBoxLayout, counts: dict[str, Any],
                          display_names: dict[str, str], keys: list[str],
                          counter_key: str) -> None:
        detail_labels = {
            "completed": ("✓ Archivos completados", "#28a745", "completed_files"),
            "warnings": ("⚠ Advertencias", "#FF9800", "warning_messages"),
            "critical": ("✗ Errores críticos", "#F44336", "critical_messages"),
        }
        counter_labels = {
            "completed": ("✓ Archivos completados", "#28a745"),
            "warnings": ("⚠ Advertencias", "#FF9800"),
            "critical": ("✗ Errores críticos", "#F44336"),
        }
        for key in keys:
            name = display_names.get(key, key)
            data = counts.get(key, {})
            header = QLabel(f"<b>{name}</b>")
            header.setStyleSheet("font-size: 13px; color: #9CDCFE;")
            layout.addWidget(header)

            if counter_key in detail_labels:
                label_text, color, list_key = detail_labels[counter_key]
                entries = data.get(list_key, [])
                if not entries:
                    empty = QLabel("Sin eventos registrados aún.")
                    empty.setStyleSheet("color: #888888; font-size: 12px;")
                    layout.addWidget(empty)
                    continue
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                name_lbl = QLabel(label_text)
                name_lbl.setStyleSheet("color: #C7C7C7; font-size: 12px;")
                val_lbl = QLabel(str(len(entries)))
                val_lbl.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: bold;")
                row_layout.addWidget(name_lbl)
                row_layout.addStretch()
                row_layout.addWidget(val_lbl)
                layout.addWidget(row)
                for entry in entries:
                    item = QLabel(entry)
                    item.setWordWrap(True)
                    item.setStyleSheet("color: #A8A8A8; font-size: 11px;")
                    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                    layout.addWidget(item)
                continue

            if not any(v for v in data.values()):
                empty = QLabel("Sin eventos registrados aún.")
                empty.setStyleSheet("color: #888888; font-size: 12px;")
                layout.addWidget(empty)
                continue

            for c_key, (label_text, c_color) in counter_labels.items():
                value = data.get(c_key, 0)
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                name_lbl = QLabel(label_text)
                name_lbl.setStyleSheet("color: #C7C7C7; font-size: 12px;")
                val_lbl = QLabel(str(value))
                val_lbl.setStyleSheet(f"color: {c_color}; font-size: 13px; font-weight: bold;")
                row_layout.addWidget(name_lbl)
                row_layout.addStretch()
                row_layout.addWidget(val_lbl)
                layout.addWidget(row)
