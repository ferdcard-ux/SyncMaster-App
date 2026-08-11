# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

from __future__ import annotations

import os
import re
import shutil
import time
from typing import Any

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QCursor,
    QEnterEvent,
    QFont,
    QIcon,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.paths import get_rclone_bisync_cache_dir
from managers.rclone_service import ETA_PATTERN, PROGRESS_PATTERN, SPEED_PATTERN, RcloneServiceManager
from ui.log_dialog import LogDialog
from ui.settings_dialog import SettingsDialog
from ui.stats_panel import STATUS_IN_PLAIN_LANGUAGE, StatsCounterButton, StatsDetailDialog


# Widget personalizado que dibuja un anillo de progreso circular para cada servicio
class CircularProgress(QWidget):
    clicked = pyqtSignal()

    def __init__(self, label_text: str, size: int = 150, parent: QWidget | None = None) -> None:
        """Initialize the circular progress ring widget.

        Args:
            label_text: Display label shown inside the ring.
            size: Diameter of the widget in pixels.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.percent = 0
        self.label = label_text
        self._arc_color = QColor("#4CAF50") # Color base interno
        self.target_color_hex = "#4CAF50"
        self.event_type = "progress"
        self.event_icon = ""
        self.speed = ""
        self.eta = ""
        self._size = size
        self.status_text = ""
        self.status_color = QColor("#E0E0E0")
        self.setFixedSize(self._size, self._size)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self._hovered = False
        self._hover_action_text = ""
        self._hover_action_color = QColor("#4CAF50")

        self.color_anim = QPropertyAnimation(self, b"arcColor")
        self.color_anim.setDuration(500)
        self.color_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self._blink_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(800)
        self._blink_timer.timeout.connect(self._toggle_blink)

    @pyqtProperty(QColor)
    def arcColor(self):
        return self._arc_color

    @arcColor.setter
    def arcColor(self, color: QColor | str) -> None:
        self._arc_color = QColor(color)
        self.status_color = self._arc_color
        self.update()

    def _animate_to(self, target_hex: str) -> None:
        if self.target_color_hex == target_hex:
            return
        self.target_color_hex = target_hex
        current = QColor(self._arc_color)
        self.color_anim.stop()
        self.color_anim.setStartValue(current)
        self.color_anim.setEndValue(QColor(target_hex))
        self.color_anim.start()

    def setValue(self, value: int) -> None:
        """Set the progress percentage (clamped to 0-100).

        Args:
            value: Progress percentage to display.
        """
        self.percent = max(0, min(100, value))
        self.update()

    def set_status(self, status_text: str) -> None:
        """Define el texto de estado y dispara la animación de color del arco."""
        self.status_text = status_text
        s = status_text.lower()
        if "error" in s or "sin conexión" in s:
            target = "#F44336"
            self.stop_blinking()
        elif "sincronizando" in s or "escaneando" in s:
            target = "#04F8F5"
            self.stop_blinking()
        elif "sincronizado" in s or "activo" in s:
            target = "#4CAF50"
            self.stop_blinking()
        elif "en espera" in s:
            target = "#C1F804"
            self.start_blinking()
        elif "paus" in s:
            target = "#f7e05f"
            self.stop_blinking()
        elif "limitado" in s or "advertencia" in s:
            target = "#FF9800"
            self.stop_blinking()
        else:
            target = "#4CAF50"
            self.stop_blinking()

        self._animate_to(target)

    def set_event(self, event_type: str) -> None:
        """Actualiza ícono y parpadeo según el tipo de evento. NO controla el color del arco."""
        self.event_type = event_type

        if event_type == "waiting":
            self.event_icon = ""
            self.start_blinking()
        elif event_type == "warning":
            self.event_icon = "⚠️"
            self.stop_blinking()
        elif event_type == "error":
            self.event_icon = "🛑"
            self.stop_blinking()
        else:
            self.event_icon = ""
            self.stop_blinking()

        self.update()

    def start_blinking(self) -> None:
        """Start the arc blink animation."""
        if not self._blink_timer.isActive():
            self._blink_visible = True
            self._blink_timer.start()

    def stop_blinking(self) -> None:
        """Stop the arc blink animation and restore visibility."""
        self._blink_timer.stop()
        self._blink_visible = True
        self.update()

    def _toggle_blink(self) -> None:
        self._blink_visible = not self._blink_visible
        self.update()

    def setInfo(self, speed: str | None, eta: str | None) -> None:
        """Update the speed and ETA text displayed in the ring.

        Args:
            speed: Transfer speed string (e.g. '10 MiB/s'), or None.
            eta: Estimated time remaining string, or None.
        """
        self.speed = speed or ""
        self.eta = eta or ""
        self.update()

    def set_hover_action(self, text: str, color: QColor | str = "#4CAF50") -> None:
        self._hover_action_text = text
        self._hover_action_color = QColor(color)

    def enterEvent(self, event: QEnterEvent | None) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent | None) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if self._hover_action_text:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the circular progress arc, status text, and event icons."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        margin = 20
        arc_rect = rect.adjusted(margin // 2, margin // 2, -margin // 2, -margin // 2)

        # 1. Fondo interno (Círculo oscuro)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1E1E1E"))
        inner_m = margin + 4
        painter.drawEllipse(rect.adjusted(inner_m // 2, inner_m // 2, -inner_m // 2, -inner_m // 2))

        # 2. Carril de fondo (Gris tenue) - Siempre visible para dar estructura
        bg_pen = QPen(QColor("#2D2D2D"), 10)
        painter.setPen(bg_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(arc_rect)

        # 3. Arco de progreso con color del estado
        # Lógica: Si hay progreso real (>0), mostrar el arco proporcional.
        # Si no hay progreso pero el estado es activo/error/warning, mostrar el anillo completo (100%).
        span_val = 0
        if self.percent > 0:
            span_val = self.percent
        elif self.status_text and self.status_text.lower() not in ["", "listo"]:
            span_val = 100

        if not self._blink_visible:
            span_val = 0

        if span_val > 0:
            prog_pen = QPen(self._arc_color, 10)
            prog_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(prog_pen)
            span = int(360 * span_val / 100)
            # Dibujar desde las 12:00 (90 grados) en sentido horario
            painter.drawArc(arc_rect, 90 * 16, -span * 16)

        # 4. Texto central: cuando está hovereado, solo mostrar la acción
        cx = rect.center().x()
        cy = rect.center().y()

        if self._hovered and self._hover_action_text:
            overlay_color = QColor(self._hover_action_color)
            overlay_color.setAlpha(50)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(overlay_color)
            painter.drawEllipse(rect.adjusted(inner_m // 2, inner_m // 2, -inner_m // 2, -inner_m // 2))

            action_font = QFont("Segoe UI", 12)
            action_font.setBold(True)
            painter.setFont(action_font)
            painter.setPen(self._hover_action_color)
            action_rect = QRectF(cx - 70, cy - 14, 140, 28)
            painter.drawText(action_rect, Qt.AlignmentFlag.AlignCenter, self._hover_action_text)
        else:
            offset_y = 6 if self.event_icon else 0

            if self.event_icon:
                icon_font = QFont("Segoe UI", 16)
                icon_font.setBold(True)
                painter.setFont(icon_font)
                painter.setPen(QColor("#E0E0E0"))
                icon_rect = QRectF(cx - 30, cy - 28, 60, 24)
                painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self.event_icon)

            if self.status_text:
                status_font = QFont("Segoe UI", 9)
                status_font.setBold(True)
                painter.setFont(status_font)
                painter.setPen(self.status_color)
                status_rect = QRectF(cx - 60, cy - 10 + offset_y, 120, 24)
                painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, self.status_text)

            if self.percent > 0:
                pct_font = QFont("Segoe UI", 11)
                pct_font.setBold(True)
                painter.setFont(pct_font)
                painter.setPen(self.status_color)
                pct_rect = QRectF(cx - 60, cy + 14 + offset_y, 120, 24)
                painter.drawText(pct_rect, Qt.AlignmentFlag.AlignCenter, f"{self.percent}%")


# Ventana principal de la app (gestiona la UI, tarjetas de sincronización y métricas)
class MainWindow(QMainWindow):
    MODE_ICONS: dict[str, str] = {
        "bisync": "↔",
        "copy": "↑",
        "sync": "⇄"
    }
    MODE_COLORS: dict[str, str] = {
        "bisync": "#9CDCFE",
        "copy": "#8ad1ff",
        "sync": "#f0d83a"
    }
    SERVICE_BRACKET_PATTERN: re.Pattern[str] = re.compile(r'^\[([^\]]+)\]')
    SERVICE_PREFIX_PATTERN: re.Pattern[str] = re.compile(r'^([^:\[\]]+):')
    def __init__(self, config_manager: Any, onedrive_manager: Any, gdrive_manager: Any, local_manager: Any, version: str, tray: QSystemTrayIcon | None, rclone_managers: list[RcloneServiceManager] | None = None) -> None:
        """Initialize the main application window.

        Args:
            config_manager: Application configuration manager.
            onedrive_manager: OneDrive sync service manager.
            gdrive_manager: Google Drive sync service manager.
            local_manager: Local folder sync service manager.
            version: Application version string.
            tray: System tray icon for notifications, or None.
            rclone_managers: Optional list of additional Rclone service managers.
        """
        super().__init__()
        self.config_manager = config_manager
        self.onedrive_manager = onedrive_manager
        self.gdrive_manager = gdrive_manager
        self.local_manager = local_manager
        self.version = version
        self.tray = tray
        self.rclone_managers = rclone_managers or []
        self.rclone_manager_map: dict[str, RcloneServiceManager] = {}
        self._connected_rclone_names: set[str] = set()
        self.notification_cooldown = 60
        self.last_notifications: dict[str, float] = {}
        self.display_names = {
            "local_sync": "Local (Rclone)",
            "gdrive": "Google Drive (Rclone)",
            "onedrive": "OneDrive (RClone)"
        }

        self.setWindowTitle(f"Sync Master v{self.version} - Monitor en Tiempo Real")
        self.resize(1200, 720)
        self.setStyleSheet("""
            background-color: #1E1E1E;
            color: #E0E0E0;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            font-size: 13px;
            QToolTip { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #4CAF50; padding: 4px; font-size: 12px; }
        """)

        # Icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets/logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # UI Elements storage
        self.status_labels: dict[str, QLabel] = {}
        self.interval_labels: dict[str, QLabel] = {}
        self.last_sync_labels: dict[str, QLabel] = {}
        self.mode_labels: dict[str, QLabel] = {}
        self.last_statuses: dict[str, str] = {}
        self.service_buttons: dict[str, QPushButton] = {}
        self.service_managers: dict[str, object] = {}
        self.service_pause_states: dict[str, bool] = {}
        self.stats_counts = {"completed": 0, "warnings": 0, "critical": 0}
        self.stats_by_service: dict[str, Any] = {}
        self.card_width = 260
        self.card_height = 220
        self.card_frames: list[QWidget] = []
        self.base_button_style = (
            "QPushButton { background-color: #2D2D2D; color: #E0E0E0; padding: 6px 12px; "
            "border: 1px solid #3C3C3C; border-radius: 5px; text-align: center; font-size: 13px; }"
            "QPushButton:hover { background-color: #383838; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
            "QPushButton:pressed { background-color: #1E1E1E; }"
        )
        self.icon_size = QSize(16, 16)
        self.general_standby_name = "Sync Master"
        self.pause_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
        self.play_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        self.toggle_pause_style = (
            "QPushButton { background-color: #2d7a33; color: #ffffff; padding: 6px 12px; "
            "border: 1px solid #256026; border-radius: 5px; font-size: 13px; }"
            "QPushButton:hover { background-color: #3a9c4b; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
        )
        self.toggle_paused_style = (
            "QPushButton { background-color: #f0d83a; color: #1e1e1e; padding: 6px 12px; "
            "border: 1px solid #b89f00; border-radius: 5px; font-size: 13px; }"
            "QPushButton:hover { background-color: #f7e05f; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
        )
        self.mount_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        self.unmount_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DriveHDIcon)
        self.service_mount_states: dict[str, bool] = {}
        self.toggle_mount_style = (
            "QPushButton { background-color: #2d7a33; color: #ffffff; padding: 6px 12px; "
            "border: 1px solid #256026; border-radius: 5px; font-size: 13px; }"
            "QPushButton:hover { background-color: #3a9c4b; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
        )
        self.toggle_mounted_style = (
            "QPushButton { background-color: #a83232; color: #ffffff; padding: 6px 12px; "
            "border: 1px solid #7a2525; border-radius: 5px; font-size: 13px; }"
            "QPushButton:hover { background-color: #c93a3a; border-color: #FF5252; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #FF5252; }"
        )
        self.sync_btn_focus_style = (
            "QPushButton { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #4A4A4A; border-radius: 5px; padding: 6px 12px; font-size: 13px; }"
            "QPushButton:hover { background-color: #383838; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
        )
        self.icon_button_style = (
            "QPushButton { background-color: transparent; border: none; color: #E0E0E0; }"
            "QPushButton:hover { color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; border-radius: 18px; }"
            "QPushButton:pressed { color: #A5D6A7; }"
        )
        self.dialog_button_style = (
            "QPushButton { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #3C3C3C; border-radius: 5px; padding: 6px 12px; }"
            "QPushButton:hover { background-color: #383838; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
            "QPushButton:pressed { background-color: #1E1E1E; }"
            "QDialogButtonBox QPushButton { min-width: 90px; }"
        )
        self.progress_ring_size = 150
        self.progress_widgets: dict[str, CircularProgress] = {}
        self.quota_labels: dict[str, dict[str, QLabel]] = {}

        self.setup_ui()
        self.connect_signals()
        self.reload_rclone_services(initial=True)

        # Populate service_managers dict with all managers (standard + rclone)
        self._populate_service_managers()

        # Start timers (initialize UI state)
        self.update_initial_info()
        self.onedrive_manager.start_timer()
        self.gdrive_manager.start_timer()
        self.local_manager.start_timer()
        for manager in self.rclone_managers:
            manager.start_timer()

        self.log_dialog = LogDialog(self)

        QTimer.singleShot(0, self.show_welcome_if_needed)

    def setup_ui(self) -> None:
        """Initialize and lay out the dashboard cards, monitor panel, and controls."""
        # Inicializa y distribuye los componentes principales de la interfaz gráfica
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        # No extra top bar; Info button lives in the bottom control bar.

        # 1. Dashboard Area (Top)
        dashboard_group = QFrame()
        dashboard_group.setStyleSheet("background-color: transparent;")
        dash_layout = QVBoxLayout()
        dash_layout.setContentsMargins(0, 0, 0, 0)
        dash_layout.setSpacing(0)
        dashboard_group.setLayout(dash_layout)

        self.cards_container = QWidget()
        self.cards_layout = QHBoxLayout()
        self.cards_layout.setSpacing(5)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_container.setLayout(self.cards_layout)
        self.cards_container.setStyleSheet("background-color: transparent;")

        # El alto de la tarjeta ajustado a los elementos (Ring=150 + Botón=36 + 5 Labels=100 + Paddings=50 = ~340)
        card_stack_height = 360
        self.cards_container.setFixedHeight(card_stack_height)

        self.cards_scroll = QScrollArea()
        self.cards_scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setWidget(self.cards_container)
        self.cards_scroll.setFixedHeight(card_stack_height)

        nav_layout = QHBoxLayout()
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(40, 40)
        self.prev_btn.clicked.connect(self.scroll_previous)
        self.prev_btn.setStyleSheet(self.icon_button_style)
        self.prev_btn.setToolTip("Ver la tarjeta anterior")
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(40, 40)
        self.next_btn.clicked.connect(self.scroll_next)
        self.next_btn.setStyleSheet(self.icon_button_style)
        self.next_btn.setToolTip("Ver la siguiente tarjeta")
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.cards_scroll)
        nav_layout.addWidget(self.next_btn)

        dash_layout.addLayout(nav_layout)

        main_layout.addWidget(dashboard_group)
        separator = QFrame()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #2D2D2D; border: none;")
        main_layout.addWidget(separator)

        monitor_container = QWidget()
        monitor_container.setStyleSheet("background-color:#1E1E1E;")
        monitor_layout = QVBoxLayout()
        monitor_layout.setContentsMargins(40, 10, 0, 0)
        monitor_container.setLayout(monitor_layout)

        monitor_title = QLabel("Panel de Monitoreo")
        monitor_title.setStyleSheet("color:#E0E0E0; font-weight: bold; margin-bottom: 6px;")
        monitor_layout.addWidget(monitor_title)

        counters_row = QWidget()
        counters_layout = QHBoxLayout()
        counters_layout.setSpacing(15)
        counters_layout.setContentsMargins(5, 10, 20, 10)
        counters_row.setLayout(counters_layout)
        monitor_layout.addWidget(counters_row)

        self.stats_counters = {
            "completed": self._create_counter("Archivos Completados", "0", counters_layout, "completed"),
            "warnings": self._create_counter("Advertencias", "0", counters_layout, "warnings"),
            "critical": self._create_counter("Errores Críticos", "0", counters_layout, "critical")
        }

        # Mini-log: últimas líneas de registros entre los contadores y el botón Menú
        self.mini_log = QTextEdit()
        self.mini_log.setReadOnly(True)
        # Reajustes sugeridos: duplicar altura (90), +60% ancho (600), fuente 12pt
        self.mini_log.setFixedHeight(95)
        self.mini_log.setMinimumWidth(600)
        self.mini_log.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.mini_log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mini_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.mini_log.setStyleSheet(
            "QTextEdit{background:#141414;color:#9CDCFE;font-size:12px;"
            "font-family:'Fira Code','Courier New','Consolas';border:1px solid #2D2D2D;"
            "border-radius:4px;padding:2px;outline:none;}"
        )
        counters_layout.addWidget(self.mini_log)

        counters_layout.addStretch()
        self.menu_btn = QPushButton()
        self.menu_btn.setIcon(self._create_menu_icon())
        self.menu_btn.setIconSize(QSize(28, 28))
        self.menu_btn.setToolTip("Menú")
        self.menu_btn.setFixedSize(48, 48)
        self.menu_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.menu_btn.setStyleSheet(
            "QPushButton{border-radius:24px;background-color:#2D2D2D;border:1px solid #3C3C3C;}"
            "QPushButton:hover{border-color:#4CAF50;color:#4CAF50; background-color:#383838;}"
            "QPushButton:focus-visible{outline:none;border:1px solid #4CAF50;}"
        )
        self.global_menu = self._create_global_menu()
        self.global_menu.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.menu_btn.clicked.connect(self.show_global_menu)
        counters_layout.addWidget(self.menu_btn)

        main_layout.addWidget(monitor_container)

    def show_global_menu(self) -> None:
        """Display the global context menu positioned above the menu button."""
        from PyQt6.QtCore import QPoint
        pos = self.menu_btn.mapToGlobal(QPoint(0, 0))
        menu_size = self.global_menu.sizeHint()
        # Mueve el menú hacia adentro (izquierda) y arriba, ya que el botón está en la esquina inferior
        pos.setX(pos.x() - menu_size.width() + self.menu_btn.width())
        pos.setY(pos.y() - menu_size.height())
        self.global_menu.exec(pos)

    def _create_global_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Sincronizar ahora", self.sync_ready_services)
        menu.addAction("Ver Registros Detallados", self.show_log_dialog)
        menu.addAction("Limpiar Cache RClone", self.clean_rclone_cache)
        menu.addAction("Configuración", self.open_settings)
        menu.addAction("Información", self.show_info)
        menu.addSeparator()
        menu.addAction("Salir", self.close)
        menu.setStyleSheet(
            "QMenu { background-color: #1E1E1E; border: 1px solid #3C3C3C; }"
            "QMenu::item { color: #E0E0E0; padding: 6px 18px; }"
            "QMenu::item:selected { background-color: #383838; border: 1px solid #4CAF50; }"
            "QMenu::item:focus { border: 1px solid #4CAF50; }"
        )
        return menu

    def _create_menu_icon(self) -> QIcon:
        icon_size = 32
        pixmap = QPixmap(icon_size, icon_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#4CAF50"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        margin = 6
        spacing = 8
        for i in range(3):
            y = margin + i * spacing
            painter.drawLine(margin, y, icon_size - margin, y)
        painter.end()
        return QIcon(pixmap)

    def create_service_card(self, title: str, key: str, manager: RcloneServiceManager | Any) -> QFrame:
        """Build a dashboard card widget for a single sync service.

        Args:
            title: Display name shown at the top of the card.
            key: Internal service key used for lookups.
            manager: Service manager instance controlling this service.

        Returns:
            A QFrame containing the full card layout.
        """
        frame = QFrame()
        total_height = 360
        frame.setFixedSize(self.card_width, total_height)
        frame.setStyleSheet("background-color: #2D2D2D; border-radius: 12px;")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 7, 8, 6)
        layout.setSpacing(4)
        frame.setLayout(layout)

        title_lbl = QLabel(f"<b>{title}</b>")
        title_lbl.setStyleSheet("color: #9CDCFE; font-size: 16px; margin-bottom: 2px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)

        info_row = QHBoxLayout()
        info_row.setSpacing(0)

        left_col = QVBoxLayout()
        left_col.setSpacing(2)
        self.status_labels[key] = QLabel("Estado: Desconocido")
        self.status_labels[key].setStyleSheet("color: #E0E0E0; font-size: 13px;")
        left_col.addWidget(self.status_labels[key])

        self.mode_labels[key] = QLabel("")
        self.mode_labels[key].setStyleSheet("color: #9CDCFE; font-size: 12px;")
        left_col.addWidget(self.mode_labels[key])
        self.update_service_mode_label(key)

        self.interval_labels[key] = QLabel("Intervalo: --")
        self.interval_labels[key].setStyleSheet("color: #C7C7C7; font-size: 12px;")
        left_col.addWidget(self.interval_labels[key])

        self.last_sync_labels[key] = QLabel("Ultima Sinc: Nunca")
        self.last_sync_labels[key].setStyleSheet("color: #C7C7C7; font-size: 12px;")
        left_col.addWidget(self.last_sync_labels[key])

        info_row.addLayout(left_col)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setStyleSheet("color: #3C3C3C;")
        separator.setFixedWidth(1)
        info_row.addWidget(separator)

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        q_style = "color: #C7C7C7; font-size: 12px;"
        q_val_style = "color: #E0E0E0; font-size: 12px; font-weight: bold;"
        self.quota_labels[key] = {}
        for field, default in [("total", "--"), ("used", "--"), ("free", "--"), ("trashed", "--")]:
            row = QHBoxLayout()
            row.setSpacing(2)
            lbl_name = QLabel(f"{field.capitalize()}:")
            lbl_name.setStyleSheet(q_style)
            lbl_name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_val = QLabel(default)
            lbl_val.setStyleSheet(q_val_style)
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl_name)
            row.addWidget(lbl_val)
            right_col.addLayout(row)
            self.quota_labels[key][field] = lbl_val

        info_row.addLayout(right_col)
        layout.addLayout(info_row)

        is_local = key == "local_sync"
        if is_local:
            control_btn = QPushButton("Pausar")
            control_btn.setIcon(self.pause_icon)
            control_btn.setStyleSheet(self.toggle_pause_style)
            control_btn.setToolTip("Pausar la sincronización de este servicio")
            control_btn.clicked.connect(lambda _, k=key, m=manager: self.toggle_service_pause(k, m))
            self.service_pause_states.setdefault(key, False)
        else:
            control_btn = QPushButton("Montar")
            control_btn.setIcon(self.mount_icon)
            control_btn.setStyleSheet(self.toggle_mount_style)
            control_btn.setToolTip("Montar la carpeta remota como una unidad local")
            control_btn.clicked.connect(lambda _, k=key, m=manager: self.toggle_service_mount(k, m))
            self.service_mount_states.setdefault(key, False)
        self.service_pause_states.setdefault(key, False)
        control_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_btn.setMinimumHeight(36)
        layout.addWidget(control_btn)
        self.service_buttons[key] = control_btn
        self.service_managers[key] = manager

        progress_widget = CircularProgress(self.display_names.get(key, key), size=self.progress_ring_size)
        progress_widget.clicked.connect(lambda k=key, m=manager: self.toggle_service_pause(k, m))
        progress_widget.setToolTip("Pausar o reanudar la sincronización (clic)")
        layout.addWidget(progress_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        self.progress_widgets[key] = progress_widget
        self.update_service_button(key)

        return frame

    def format_bytes(self, b: float) -> str:
        """Convert a byte count to a human-readable string with appropriate unit.

        Args:
            b: Number of bytes.

        Returns:
            Formatted string such as '1.50 GiB'.
        """
        for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
            if abs(b) < 1024.0:
                return f"{b:.2f} {unit}"
            b /= 1024.0
        return f"{b:.2f} PiB"

    def _load_persisted_quota(self) -> None:
        cache = self.config_manager.get("quota_cache", {})
        for service_key, data in cache.items():
            if self.quota_labels.get(service_key):
                self.update_quota(service_key, data, stale=True)

    def _check_quota_warning(self, service_key: str, data: dict[str, Any]) -> None:
        total = data.get("total")
        used = data.get("used")
        if total and used:
            pct = (float(used) / float(total)) * 100
            if pct > 90:
                name = self.display_names.get(service_key, service_key)
                self.append_log(
                    f"⚠️ QUOTA CRÍTICA: {name} al {pct:.0f}% — {self.format_bytes(float(used))} de {self.format_bytes(float(total))}",
                    force=True,
                )
                pw = self.progress_widgets.get(service_key)
                if pw:
                    pw.set_event("warning")

    def update_quota(self, service_key: str, data: dict[str, Any], stale: bool = False) -> None:
        """Update the quota display labels for a service and persist to cache.

        Args:
            service_key: Internal service key.
            data: Quota dict with 'total', 'used', 'free', 'trashed' values.
            stale: If True, data comes from cache (offline mode). Labels are greyed.
        """
        labels = self.quota_labels.get(service_key)
        if not labels:
            return
        stale_suffix = " (offline)" if stale else ""
        stale_color = "#888888" if stale else "#E0E0E0"
        for field in ("total", "used", "free", "trashed"):
            val = data.get(field)
            lbl = labels.get(field)
            if lbl and val is not None:
                lbl.setText(self.format_bytes(float(val)) + stale_suffix)
                lbl.setStyleSheet(f"color: {stale_color}; font-size: 12px; font-weight: bold;")
            elif lbl:
                lbl.setText("--")
        cache = self.config_manager.get("quota_cache", {})
        cache[service_key] = data
        self.config_manager.set("quota_cache", cache)
        self._check_quota_warning(service_key, data)

    def connect_signals(self) -> None:
        """Wire manager signals (status, log, progress, quota) to UI update slots."""
        # Conecta los eventos (señales) emitidos por los gestores hacia la UI
        # Local
        self.local_manager.status_changed.connect(lambda s: self.update_status("local_sync", s))
        self.local_manager.log_message.connect(self.append_log)
        self.local_manager.sync_finished.connect(lambda t: self.update_last_sync("local_sync", t))
        self.local_manager.progress_updated.connect(self.update_service_progress)
        self.local_manager.stats_event.connect(self._on_stats_event)

        # GDrive
        self.gdrive_manager.status_changed.connect(lambda s: self.update_status("gdrive", s))
        self.gdrive_manager.log_message.connect(self.append_log)
        self.gdrive_manager.sync_finished.connect(lambda t: self.update_last_sync("gdrive", t))
        self.gdrive_manager.progress_updated.connect(self.update_service_progress)
        self.gdrive_manager.credential_error.connect(self._handle_credential_error)
        self.gdrive_manager.quota_updated.connect(self.update_quota)
        self.gdrive_manager.mount_changed.connect(lambda _name, _mounted, k="gdrive": self.update_mount_button(k))
        self.gdrive_manager.stats_event.connect(self._on_stats_event)

        # OneDrive
        self.onedrive_manager.status_changed.connect(lambda s: self.update_status("onedrive", s))
        self.onedrive_manager.log_message.connect(self.append_log)
        self.onedrive_manager.sync_finished.connect(lambda t: self.update_last_sync("onedrive", t))
        if hasattr(self.onedrive_manager, "progress_updated"):
            self.onedrive_manager.progress_updated.connect(self.update_service_progress)
        if hasattr(self.onedrive_manager, "credential_error"):
            self.onedrive_manager.credential_error.connect(self._handle_credential_error)
        if hasattr(self.onedrive_manager, "quota_updated"):
            self.onedrive_manager.quota_updated.connect(self.update_quota)
        if hasattr(self.onedrive_manager, "mount_changed"):
            self.onedrive_manager.mount_changed.connect(lambda _name, _mounted, k="onedrive": self.update_mount_button(k))
        if hasattr(self.onedrive_manager, "stats_event"):
            self.onedrive_manager.stats_event.connect(self._on_stats_event)

    def connect_rclone_signals(self, manager: RcloneServiceManager, key: str) -> None:
        """Connect an Rclone manager's signals to the UI, avoiding duplicate connections.

        Args:
            manager: The Rclone service manager to connect.
            key: Service key used for UI lookups.
        """
        if manager.service_name in self._connected_rclone_names:
            return
        manager.status_changed.connect(lambda s, k=key: self.update_status(k, s))
        manager.log_message.connect(self.append_log)
        manager.sync_finished.connect(lambda t, k=key: self.update_last_sync(k, t))
        manager.progress_updated.connect(self.update_service_progress)
        manager.credential_error.connect(self._handle_credential_error)
        manager.quota_updated.connect(lambda name, data, k=key: self.update_quota(k, data))
        if hasattr(manager, "mount_changed"):
            manager.mount_changed.connect(lambda _name, _mounted, k=key: self.update_mount_button(k))
        manager.stats_event.connect(lambda _svc, cat, det, k=key: self._on_stats_event(k, cat, det))
        self._connected_rclone_names.add(manager.service_name)

    def _populate_service_managers(self) -> None:
        """Populate service_managers dict with enabled managers only."""
        self.service_managers = {}

        if self.config_manager.get("local_sync", {}).get("enabled", False):
            self.service_managers["local_sync"] = self.local_manager
        if self.config_manager.get("gdrive", {}).get("enabled", False):
            self.service_managers["gdrive"] = self.gdrive_manager
        if self.config_manager.get("onedrive", {}).get("enabled", False):
            self.service_managers["onedrive"] = self.onedrive_manager

        for manager in self.rclone_managers:
            key = f"rclone:{manager.service_name}"
            self.service_managers[key] = manager

    def build_service_cards(self) -> None:
        """Recreate all service cards from the current configuration."""
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        self.status_labels = {}
        self.interval_labels = {}
        self.last_sync_labels = {}

        entries = []

        if self.config_manager.get("local_sync", {}).get("enabled", False):
            entries.append(("local_sync", "Local (Rclone)", self.local_manager))
        if self.config_manager.get("gdrive", {}).get("enabled", False):
            entries.append(("gdrive", "Google Drive (Rclone)", self.gdrive_manager))
        if self.config_manager.get("onedrive", {}).get("enabled", False):
            entries.append(("onedrive", "OneDrive (RClone)", self.onedrive_manager))

        for manager in self.rclone_managers:
            key = f"rclone:{manager.service_name}"
            entries.append((key, manager.service_name, manager))
            self.display_names[key] = manager.service_name

        self.card_frames.clear()
        self.progress_widgets.clear()
        self.quota_labels.clear()
        self.cards_layout.addStretch()
        for _idx, (key, title, manager) in enumerate(entries):
            card = self.create_service_card(title, key, manager)
            self.cards_layout.addWidget(card)
            self.card_frames.append(card)
        self.cards_layout.addStretch()
        self._load_persisted_quota()
        self._populate_service_managers()
        self.snap_scroll_to_card(0)
        self.adjust_window_size()

    def adjust_window_size(self) -> None:
        """Resize the window to fit the visible cards and screen dimensions."""
        # Ajusta automáticamente las dimensiones de la ventana al arranque
        from PyQt6.QtGui import QGuiApplication
        screen = QGuiApplication.primaryScreen().availableGeometry()

        num_cards = len(self.card_frames)
        visible_cards = max(2, min(num_cards, 4))

        # Calcular ancho necesario: (tarjetas * ancho) + espaciados + flechas (80px) + márgenes layout principal (10px)
        content_w = (self.card_width * visible_cards) + (self.cards_layout.spacing() * (visible_cards - 1))
        total_w = content_w + 80 + 10 + 10  # 20 extra para paddings y separar elementos

        # Ajustar la altura a un valor más ajustado o al tamaño de la pantalla
        total_h = min(480, screen.height())

        self.resize(total_w, total_h)

    def snap_scroll_to_card(self, index: int) -> None:
        """Jump the card scroll area to show the card at the given index.

        Args:
            index: Zero-based card index to scroll to.
        """
        if index < 0 or not self.card_frames:
            return
        step = self.card_width + self.cards_layout.spacing()
        target = index * step
        bar = self.cards_scroll.horizontalScrollBar()
        bar.setValue(min(bar.maximum(), target))

    def scroll_previous(self) -> None:
        """Scroll the card container one card to the left."""
        bar = self.cards_scroll.horizontalScrollBar()
        step = self.card_width + self.cards_layout.spacing()
        bar.setValue(max(0, bar.value() - step))

    def scroll_next(self) -> None:
        """Scroll the card container one card to the right."""
        bar = self.cards_scroll.horizontalScrollBar()
        step = self.card_width + self.cards_layout.spacing()
        bar.setValue(min(bar.maximum(), bar.value() + step))

    def reload_rclone_services(self, initial: bool = False) -> None:
        """Load or refresh the list of dynamically-added Rclone services.

        Args:
            initial: If True, create managers from scratch; otherwise reconcile
                     the existing list against the current configuration.
        """
        # Carga o actualiza los servicios secundarios añadidos dinámicamente desde configuración
        services = self.config_manager.get("rclone_services", []) or []
        new_names = {s.get("name") for s in services if s.get("name")}

        if initial:
            if not self.rclone_managers:
                self.rclone_managers = [
                    RcloneServiceManager(self.config_manager, self.onedrive_manager.coordinator, name)
                    for name in new_names
                ]
        else:
            for manager in self.rclone_managers:
                if manager.service_name not in new_names:
                    manager.stop_timer()
                    if manager.service_name in self._connected_rclone_names:
                        self._connected_rclone_names.remove(manager.service_name)

            existing = {m.service_name: m for m in self.rclone_managers}
            self.rclone_managers = []
            for name in new_names:
                if name in existing:
                    self.rclone_managers.append(existing[name])
                else:
                    self.rclone_managers.append(RcloneServiceManager(self.config_manager, self.onedrive_manager.coordinator, name))

        self.rclone_manager_map = {m.service_name: m for m in self.rclone_managers}
        for manager in self.rclone_managers:
            self.connect_rclone_signals(manager, f"rclone:{manager.service_name}")

        self.build_service_cards()

    def update_initial_info(self) -> None:
        """Populate status, interval, and mode labels for all known services."""
        for key in list(self.interval_labels.keys()):
            if key in ["local_sync", "gdrive", "onedrive"]:
                conf = self.config_manager.get(key, {})
                interval = conf.get("interval_minutes", 15)
                enabled = conf.get("enabled", False)
            elif key.startswith("local:"):
                service_id = key.split(":", 1)[1]
                conf = self.get_local_service_config(service_id) or {}
                interval = conf.get("interval_minutes", 15)
                enabled = conf.get("enabled", False)
            else:
                service_name = key.split("rclone:", 1)[1] if "rclone:" in key else key
                conf = self.get_rclone_service_config(service_name) or {}
                interval = conf.get("interval_minutes", 15)
                enabled = conf.get("enabled", True)

            self.interval_labels[key].setText(f"Intervalo: {interval} min")
            if not enabled:
                self.status_labels[key].setText("Estado: Desactivado")
                self.status_labels[key].setStyleSheet("color: #6c757d;")
            else:
                self.status_labels[key].setText("Estado: Activo")
                self.status_labels[key].setStyleSheet("color: #28a745; font-weight: bold;")
            self.update_service_mode_label(key)

    def update_status(self, key: str, status: str) -> None:
        """Update the status label, progress ring, and trigger notifications.

        Args:
            key: Service key to update.
            status: New status text from the service manager.
        """
        # Evitar actualizaciones redundantes que reinician la animación y causan flicker
        if self.last_statuses.get(key) == status:
            return
        self.last_statuses[key] = status

        lbl = self.status_labels.get(key)
        status_lower = status.lower()

        # Corrección: El QLabel superior solo muestra Activo/Desactivado/Pausado
        is_disabled = "desactivado" in status_lower or "detenido" in status_lower
        is_paused = "pausado" in status_lower or "pausa" in status_lower
        if lbl:
            if is_paused:
                lbl.setText("Estado: Pausado")
                lbl.setStyleSheet("color: #ffc107; font-weight: bold;")
            elif is_disabled:
                lbl.setText("Estado: Desactivado")
                lbl.setStyleSheet("color: #6c757d; font-weight: bold;")
            else:
                lbl.setText("Estado: Activo")
                lbl.setStyleSheet("color: #28a745; font-weight: bold;")
            # Lenguaje cotidiano: explicar el estado real en el tooltip.
            card_title = self.display_names.get(key, key)
            explanation = STATUS_IN_PLAIN_LANGUAGE.get(status, status)
            lbl.setToolTip(f"<b>{card_title}</b>: {explanation}")

        progress_widget = self.progress_widgets.get(key)
        if progress_widget:
            # Mapear estados al evento del anillo (color del arco)
            if "sincronizando" in status_lower or "escaneando" in status_lower:
                progress_widget.set_event("start")
            elif "error" in status_lower or "sin conexión" in status_lower:
                progress_widget.set_event("error")
            elif "en espera" in status_lower:
                progress_widget.set_event("waiting")
            elif "paus" in status_lower:
                progress_widget.set_event("warning")
            elif "advertencia" in status_lower or "limitado" in status_lower:
                progress_widget.set_event("warning")

            # Mostrar texto detallado siempre en el centro del anillo (menos Activo/Desactivado base)
            skip_states = {"activo", "desactivado", "detenido"}
            if status_lower not in skip_states and not any(s == status_lower for s in skip_states):
                progress_widget.set_status(status)
            else:
                if status_lower == "activo":
                    # Si está Activo (reposo con éxito), mostrar "Sincronizado" en Verde
                    progress_widget.set_status("Sincronizado")
                elif is_disabled:
                    # Si está desactivado, limpiar status y resetear % a 0 para esconder arco
                    progress_widget.set_status("")
                    progress_widget.setValue(0)

        self.maybe_notify_status(key, status)

    def update_service_mode_label(self, key: str) -> None:
        """Refresh the mode label text and color for a service.

        Args:
            key: Service key whose mode label should be updated.
        """
        lbl = self.mode_labels.get(key)
        if not lbl:
            return
        mode = self.get_service_mode(key)
        icon = self.MODE_ICONS.get(mode, "↔")
        color = self.MODE_COLORS.get(mode, "#9CDCFE")
        lbl.setText(f"Modo: {mode.capitalize()} {icon}")
        lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")

    def get_service_mode(self, key: str) -> str:
        """Return the sync mode for a given service.

        Args:
            key: Service key (e.g. 'local_sync', 'rclone:MyDrive').

        Returns:
            Mode string such as 'bisync', 'copy', or 'sync'.
        """
        if key in ["local_sync", "gdrive", "onedrive"]:
            conf = self.config_manager.get(key, {})
            return conf.get("mode", "bisync")
        if key.startswith("local:"):
            service_id = key.split(":", 1)[1]
            conf = self.get_local_service_config(service_id) or {}
            return conf.get("mode", "bisync")
        if key.startswith("rclone:"):
            service_name = key.split(":", 1)[1]
            conf = self.get_rclone_service_config(service_name) or {}
            return conf.get("mode", "bisync")
        return "bisync"

    def update_last_sync(self, key: str, timestamp: float) -> None:
        """Update the 'last sync' label for a service.

        Args:
            key: Service key.
            timestamp: Unix timestamp of the completed sync.
        """
        lbl = self.last_sync_labels.get(key)
        if lbl:
            from datetime import datetime
            dt = datetime.fromtimestamp(timestamp)
            time_str = dt.strftime("%H:%M:%S")
            lbl.setText(f"Última Sinc: {time_str}")

    def append_log(self, message: str, *, force: bool = False) -> None:
        """Route a log message to the log dialog, mini-log, and notification system.

        Args:
            message: Log text to process.
            force: If True, bypass display filtering and always show the message.
        """
        # Punto de entrada para las salidas de texto de los gestores, encargador de procesar o descartar
        service_label = self.extract_service_name(message) or self.general_standby_name

        # Actualizar UI siempre antes de descartar (evita anillos trabados en 0%)
        self._update_progress_from_message(service_label, message)

        if not force and not self.should_display_log(message):
            return

        self.maybe_notify_log(message)
        self._send_to_log_dialog(service_label, message)

        # Actualizar mini-log del dashboard
        if hasattr(self, 'mini_log'):
            self.mini_log.append(message)
            # Limitar a las últimas 10 líneas de actividad por petición
            cursor = self.mini_log.textCursor()
            doc = self.mini_log.document()
            if doc.blockCount() > 10:
                cursor.movePosition(cursor.MoveOperation.Start)
                cursor.select(cursor.SelectionType.BlockUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar() # remove the newline
            self.mini_log.verticalScrollBar().setValue(self.mini_log.verticalScrollBar().maximum())

    def should_display_log(self, message: str) -> bool:
        """Check whether a log message should be shown in the history panel.

        Args:
            message: Raw log text to evaluate.

        Returns:
            True if the message contains actionable or eventful content.
        """
        # Verifica palabras clave permitidas o prohibidas para evitar spam en el historial del servicio
        lower = message.lower()
        noise_terms = [
            "modtime", "hashtype", "hash-type", "hash type", "building path", "no changes found",
            "updating listings", "scanning", "metadata", "checking", "path finished"
        ]
        if any(term in lower for term in noise_terms):
            return False

        # Descarta líneas de estadísticas de rclone sin transferencia activa
        # (p. ej. "0 B / 0 B, -, 0 B/s, ETA -") como capa de respaldo en la UI.
        from managers.rclone_service import STATS_NOISE_PATTERN
        if STATS_NOISE_PATTERN.search(message):
            return False

        event_terms = [
            "transferred", "transfers", "transferring", "transfer", "deleted", "deleting",
            "delete", "renamed", "renaming", "copied", "copying", "uploading", "downloading",
            "created", "moved", "resincroniz", "resync", "notice", "symlink", "onedrive", "quota",
            "iniciando", "ejecutando", "nothing to transfer",
            # Eventos de bisync
            "bisync", "error", "failed", "warning", "panic", "abort",
            "se requiere", "advertencia", "completada", "completado",
            "sincronización", "deduplicación", "auto-recuperación"
        ]
        if any(term in lower for term in event_terms):
            return True

        # Mostrar líneas de progreso de rclone (e.g. "X MiB / Y MiB, N%")
        if "%" in message and "/" in message:
            return True

        if "[od]" in lower or "[od info/err]" in lower or "[od prompt]" in lower or "[od prompt stderr]" in lower:
            return True

        if self.is_error_message(message):
            return True

        return False

    def _update_progress_from_message(self, service_label: str, text: str) -> None:
        payload = self._parse_progress_payload(text)
        if not payload:
            return
        key = self._resolve_progress_key(service_label)
        if key:
            self.update_service_progress(key, payload)

    def _parse_progress_payload(self, text: str) -> dict[str, Any] | None:
        match = PROGRESS_PATTERN.search(text)
        if not match:
            return None
        data = {"percent": int(match.group(1))}
        speed = SPEED_PATTERN.search(text)
        if speed:
            data["speed"] = speed.group(1)
        eta = ETA_PATTERN.search(text)
        if eta:
            data["eta"] = eta.group(1)
        data["alert"] = bool(re.search(r"error|failed|panic", text, re.IGNORECASE))
        return data

    def _resolve_progress_key(self, label: str) -> str | None:
        label_lower = (label or "").lower()
        for key, display in self.display_names.items():
            if not display:
                continue
            display_lower = display.lower()
            if label_lower == display_lower or label_lower in display_lower:
                return key
        if label_lower == "local":
            return "local_sync"
        if "gdrive" in label_lower:
            return "gdrive"
        if "onedrive" in label_lower or "od" == label_lower:
            return "onedrive"
        return None

    def is_error_message(self, message: str) -> bool:
        """Determine whether a log message indicates an error condition.

        Args:
            message: Log text to check.

        Returns:
            True if the message contains error-related keywords.
        """
        lower = message.lower()
        return any(term in lower for term in ["error", "failed", "critico", "critical", "sin conexión", "panic"])

    def extract_service_name(self, message: str) -> str:
        """Parse a service name from a log message prefix or bracket tag.

        Args:
            message: Raw log text potentially prefixed with '[Service]' or 'Service:'.

        Returns:
            Normalized display name, or the default standby name if unrecognised.
        """
        if not message:
            return self.general_standby_name
        name = None
        match = self.SERVICE_BRACKET_PATTERN.match(message)
        if match:
            name = match.group(1)
        else:
            match = self.SERVICE_PREFIX_PATTERN.match(message)
            if match:
                name = match.group(1)
        if name:
            import re
            name = re.sub(r'(?i)\s*(error|red|dedupe|info/err|prompt stderr|prompt|info)\s*$', '', name).strip()

            # Unificar nombres (Alias vs Canonical) para evitar pestañas duplicadas
            name_lower = name.lower()
            if name_lower == "local":
                return self.display_names.get("local_sync", "Local (Rclone)")
            if name_lower == "gdrive":
                return self.display_names.get("gdrive", "Google Drive (Rclone)")
            if name_lower == "od" or name_lower == "onedrive":
                return self.display_names.get("onedrive", "OneDrive (RClone)")

            for _key, display in self.display_names.items():
                if display and name_lower == display.lower():
                    return display

            return name
        return self.general_standby_name

    def open_settings(self) -> None:
        """Open the settings dialog and reload services if changes are saved."""
        dialog = SettingsDialog(self.config_manager, self)
        try:
            if dialog.exec():
                self.reload_rclone_services()
                self.update_initial_info()
                self.onedrive_manager.start_timer()
                self.gdrive_manager.start_timer()
                self.local_manager.start_timer()
                for manager in self.rclone_managers:
                    manager.start_timer()
        except Exception:
            import logging
            logging.exception("Error al aplicar configuración")

    def clean_rclone_cache(self) -> None:
        """Prompt for services, delete the bisync cache, and optionally resync."""
        selected_services = self._select_cache_services()
        if selected_services is None:
            return
        if not selected_services:
            QMessageBox.warning(self, "Sin servicios", "Selecciona al menos un servicio configurado.")
            return

        cache_dir = get_rclone_bisync_cache_dir()
        cleaned = False
        if os.path.isdir(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
            cleaned = True

        services_text = ", ".join(name for name, _ in selected_services)
        if cleaned:
            self.append_log(f"RClone: Caché de bisync eliminada para {services_text}.", force=True)
        else:
            self.append_log(f"RClone: No se encontró caché para {services_text}.", force=True)

        if self.tray:
            self.tray.show_message(
                "Sync Master",
                f"Cache RClone limpiada para: {services_text}.",
                QSystemTrayIcon.MessageIcon.Information
            )

        resync_now = QMessageBox.question(
            self,
            "Re-sincronización",
            "¿Deseas resincronizar ahora?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if resync_now == QMessageBox.StandardButton.Yes:
            for label, manager in selected_services:
                self._force_resync_service(manager, label)
        else:
            for label, manager in selected_services:
                self._schedule_resync_service(manager, label)

    def _select_cache_services(self) -> list[tuple[str, Any]] | None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Limpiar Caché RClone")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Selecciona los servicios cuya caché deseas limpiar:"))

        service_map = [
            ("Local", self.local_manager),
            ("GDrive", self.gdrive_manager),
            ("OneDrive", self.onedrive_manager),
        ]
        for manager in self.rclone_managers:
            service_map.append((manager.service_name, manager))

        checkboxes = []
        for label, manager in service_map:
            cb = QCheckBox(label)
            cb.setStyleSheet("color: #E0E0E0; font-size: 13px;")
            cb.setChecked(bool(manager))
            if manager is None:
                cb.setEnabled(False)
                cb.setToolTip("Servicio no configurado")
            layout.addWidget(cb)
            checkboxes.append((label, manager, cb))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        dialog.setStyleSheet(
            "QWidget { background-color: #1E1E1E; color: #E0E0E0; font-size: 13px; }"
            + self.dialog_button_style
        )
        dialog.resize(360, 240)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None

        return [(label, manager) for label, manager, cb in checkboxes if cb.isChecked() and manager]

    def _force_resync_service(self, manager: Any, label: str) -> None:
        if hasattr(manager, "force_resync"):
            manager.force_resync()
            self.append_log(f"{label}: Re-sincronización inmediata iniciada.", force=True)
        else:
            self.append_log(f"{label}: No se puede iniciar re-sincronización inmediata.", force=True)

    def _schedule_resync_service(self, manager: Any, label: str) -> None:
        if hasattr(manager, "force_resync_next"):
            manager.force_resync_next = True
            self.append_log(f"{label}: --resync programado para la próxima ejecución automática.", force=True)
        else:
            self.append_log(f"{label}: No se puede programar --resync automáticamente.", force=True)

    def toggle_service_pause(self, key: str, manager: Any) -> None:
        """Toggle a service between paused and running states.

        Args:
            key: Service key.
            manager: The service manager instance to control.
        """
        if self.service_pause_states.get(key, False):
            self.resume_service(key, manager)
        else:
            self.pause_service(key, manager)

    def toggle_service_mount(self, key: str, manager: Any) -> None:
        if self.service_mount_states.get(key, False):
            self.unmount_service(key, manager)
        else:
            self.mount_service(key, manager)

    def mount_service(self, key: str, manager: Any) -> None:
        mount_fn = getattr(manager, "mount", None)
        if not callable(mount_fn):
            self.append_log(f"{self.display_names.get(key, key)}: Este servicio no soporta montaje.")
            return
        self.service_mount_states[key] = True
        mount_fn()
        self.update_mount_button(key)

    def unmount_service(self, key: str, manager: Any) -> None:
        unmount_fn = getattr(manager, "unmount", None)
        if not callable(unmount_fn):
            return
        self.service_mount_states[key] = False
        unmount_fn()
        self.update_mount_button(key)

    def update_mount_button(self, key: str) -> None:
        btn = self.service_buttons.get(key)
        if not btn:
            return
        if self.service_mount_states.get(key, False):
            btn.setText("Desmontar")
            btn.setStyleSheet(self.toggle_mounted_style)
            btn.setIcon(self.unmount_icon)
            btn.setToolTip("Desmontar la carpeta remota de la unidad local")
        else:
            btn.setText("Montar")
            btn.setStyleSheet(self.toggle_mount_style)
            btn.setIcon(self.mount_icon)
            btn.setToolTip("Montar la carpeta remota como una unidad local")

    def pause_service(self, key: str, manager: Any) -> None:
        """Pause a sync service by stopping its timer and related backoff timers.

        Args:
            key: Service key.
            manager: The service manager instance to pause.
        """
        self.service_pause_states[key] = True
        manager.stop_timer()
        if hasattr(manager, "_quota_backoff_timer"):
            manager._quota_backoff_timer.stop()
        if hasattr(manager, "_wait_retry_timer"):
            manager._wait_retry_timer.stop()
        self.update_service_button(key)
        self.update_status(key, "Pausado")

    def resume_service(self, key: str, manager: Any) -> None:
        """Resume a paused sync service by restarting its timer.

        Args:
            key: Service key.
            manager: The service manager instance to resume.
        """
        self.service_pause_states[key] = False
        manager.start_timer()
        self.update_service_button(key)
        self.update_status(key, "Activo")

    def update_service_button(self, key: str) -> None:
        """Refresh the pause/resume button label, style, and progress widget hover.

        Args:
            key: Service key.
        """
        pw = self.progress_widgets.get(key)
        if pw:
            paused = self.service_pause_states.get(key, False)
            pw.set_hover_action(
                "Reanudar" if paused else "Pausar",
                QColor("#f7e05f") if paused else QColor("#4CAF50")
            )
            pw.setToolTip(
                "Reanudar la sincronización (clic)" if paused
                else "Pausar la sincronización (clic)"
            )
        if key != "local_sync":
            return
        btn = self.service_buttons.get(key)
        if not btn:
            return
        if self.service_pause_states.get(key, False):
            btn.setText("Reanudar")
            btn.setStyleSheet(self.toggle_paused_style)
            btn.setIcon(self.play_icon)
            btn.setToolTip("Reanudar la sincronización de este servicio")
        else:
            btn.setText("Pausar")
            btn.setStyleSheet(self.toggle_pause_style)
            btn.setIcon(self.pause_icon)
            btn.setToolTip("Pausar la sincronización de este servicio")

    def sync_ready_services(self) -> None:
        """Trigger a manual sync on all enabled and non-paused services."""
        ready_services = []
        for key, manager in self.service_managers.items():
            if self.service_pause_states.get(key, False):
                continue
            if not self.is_service_enabled(key):
                continue
            ready_services.append((key, manager))

        if not ready_services:
            self.append_log("Sync Master: No hay servicios activos para sincronizar.")
            return

        for key, manager in ready_services:
            sync_fn = getattr(manager, "sync", None)
            if callable(sync_fn):
                self.update_status(key, "Sincronizando")
                sync_fn()
                self.append_log(f"{self.display_names.get(key, key)}: Sincronización manual iniciada.")

    def show_log_dialog(self) -> None:
        """Display the detailed log dialog window."""
        self.log_dialog.show()

    def show_welcome_if_needed(self) -> None:
        """Show the first-run welcome message if it has not been displayed yet."""
        gen_conf = self.config_manager.get("general", {})
        if gen_conf.get("welcome_shown", False):
            return

        message = (
            f"Sync Master - Versión: {self.version}\n"
            "Desarrollador: FerDev\n"
            "Contacto: ferdcard@gmail.com\n\n"
            "Importante: Sync Master utiliza los servicios de software de terceros como RClone y el cliente de OneDrive "
            "para ejecutar la configuración y sincronización de directorios. Es indispensable que dichos servicios se "
            "encuentren instalados en su sistema para el correcto funcionamiento de esta app.\n\n"
            "El desarrollador de Sync Master no es responsable por el uso y/o disponibilidad del software adicional anteriormente mencionado."
        )
        QMessageBox.information(self, "Bienvenido a Sync Master", message)
        gen_conf["welcome_shown"] = True
        self.config_manager.set("general", gen_conf)

    def show_info(self) -> None:
        """Display the application information dialog."""
        info = QMessageBox(self)
        info.setWindowTitle("Información de la App")
        info.setText(
            "Autor: Miguel Fernando Cárdenas Alvear.\n"
            "Licencia: Evaluación Privada / Propietaria.\n\n"
            "Solución Propietaria FerDev para sincronizar carpetas locales y servicios en la nube, "
            "con monitoreo en tiempo real, estrategias de recuperación y control de estados protegidos."
        )
        info.setStyleSheet(
            "QMessageBox { background-color: #1E1E1E; color: #E0E0E0; }"
            + self.dialog_button_style
        )
        info.exec()

    def get_rclone_service_config(self, service_name: str) -> dict[str, Any] | None:
        """Look up an Rclone service configuration by name.

        Args:
            service_name: The registered name of the Rclone service.

        Returns:
            Service config dict, or None if not found.
        """
        services = self.config_manager.get("rclone_services", []) or []
        for service in services:
            if service.get("name") == service_name:
                return service
        return None

    def get_local_service_config(self, service_id: str) -> dict[str, Any] | None:
        """Look up a local service configuration by ID.

        Args:
            service_id: The unique ID of the local service.

        Returns:
            Service config dict, or None if not found.
        """
        services = self.config_manager.get("local_services", []) or []
        for service in services:
            if service.get("id") == service_id:
                return service
        return None

    def maybe_notify_status(self, key: str, status: str) -> None:
        """Send a tray notification if the status change warrants one.

        Args:
            key: Service key.
            status: New status text.
        """
        if not self.tray:
            return

        level = None
        status_lower = status.lower()
        if "error" in status_lower or "sin conexión" in status_lower:
            level = "critical"
        elif "en espera" in status_lower or "resync" in status_lower or "limitado" in status_lower:
            level = "warning"

        if not level:
            return

        display_name = self.display_names.get(key, key)
        message = f"{display_name}: {status}"
        self.send_notification(level, "Sync Master", message, f"{level}:{key}")

    def maybe_notify_log(self, message: str) -> None:
        """Send a tray notification for notable log entries.

        Args:
            message: Log text to evaluate for notification triggers.
        """
        if not self.tray:
            return

        msg_lower = message.lower()
        if "re-sincronización" in msg_lower or "resync" in msg_lower:
            self.send_notification("warning", "Sync Master", message, "warning:log")
        elif "error crítico" in msg_lower or "critico" in msg_lower:
            self.send_notification("critical", "Sync Master", message, "critical:log")

    def _handle_credential_error(self, message: str) -> None:
        from PyQt6.QtWidgets import QMessageBox
        self.send_notification("critical", "Sync Master", f"Error de autenticación: {message}", "cred")
        QMessageBox.critical(self, "Error de credenciales",
            f"Se detectó un problema de autenticación en un servicio:\n\n{message}\n\n"
            "Revisa la configuración del servicio y las credenciales.")

    def send_notification(self, level: str, title: str, message: str, dedupe_key: str | None = None) -> None:
        """Send a tray notification with cooldown-based deduplication.

        Args:
            level: Severity level ('critical', 'warning', or 'info').
            title: Notification title.
            message: Notification body text.
            dedupe_key: Optional key to prevent repeated notifications.
        """
        now = time.time()
        key = dedupe_key or f"{level}:{title}"
        last_time = self.last_notifications.get(key, 0)
        if now - last_time < self.notification_cooldown:
            return
        self.last_notifications[key] = now

        icon = QSystemTrayIcon.MessageIcon.Information
        if level == "critical":
            icon = QSystemTrayIcon.MessageIcon.Critical
        elif level == "warning":
            icon = QSystemTrayIcon.MessageIcon.Warning

        self.tray.show_message(title, message, icon)

    def is_service_enabled(self, key: str) -> bool:
        """Check whether a service is enabled in the current configuration.

        Args:
            key: Service key (e.g. 'local_sync', 'rclone:MyDrive').

        Returns:
            True if the service is enabled.
        """
        if key in ["local_sync", "gdrive", "onedrive"]:
            conf = self.config_manager.get(key, {})
            return conf.get("enabled", False)
        if key.startswith("local:"):
            service_id = key.split(":", 1)[1]
            conf = self.get_local_service_config(service_id) or {}
            return conf.get("enabled", False)
        if key.startswith("rclone:"):
            service_name = key.split(":", 1)[1]
            conf = self.get_rclone_service_config(service_name) or {}
            return conf.get("enabled", True)
        return True

    def _create_counter(self, title: str, value: str, layout: QHBoxLayout, counter_key: str) -> StatsCounterButton:
        def _open_detail() -> None:
            self._show_stats_detail(counter_key)

        button = StatsCounterButton(title, value, counter_key, _open_detail)
        layout.addWidget(button)
        return button

    def _show_stats_detail(self, counter_key: str) -> None:
        """Open the plain-language detail dialog for a given counter."""
        titles = {
            "completed": "Archivos Completados",
            "warnings": "Advertencias",
            "critical": "Errores",
        }
        dialog = StatsDetailDialog(
            titles.get(counter_key, "Detalle de contadores"),
            dict(self.stats_by_service),
            dict(self.display_names),
            self,
            counter_key=counter_key,
        )
        dialog.exec()

    def _on_stats_event(self, service: str, category: str, detail: str) -> None:
        """Register a stats event (file transferred, warning, error) per service.

        Args:
            service: Service key.
            category: One of "completed", "warnings" or "critical".
            detail: File name (completed) or raw log line (warnings/critical).
        """
        if category not in self.stats_counts:
            return
        service_data = self.stats_by_service.setdefault(
            service,
            {
                "completed": 0,
                "warnings": 0,
                "critical": 0,
                "completed_files": [],
                "warning_messages": [],
                "critical_messages": [],
            },
        )
        if category == "completed":
            service_data["completed"] = service_data.get("completed", 0) + 1
            service_data["completed_files"].append(detail)
        elif category == "warnings":
            service_data["warnings"] = service_data.get("warnings", 0) + 1
            service_data["warning_messages"].append(detail)
        else:
            service_data["critical"] = service_data.get("critical", 0) + 1
            service_data["critical_messages"].append(detail)
        self.stats_counts[category] += 1
        counter_lbl = self.stats_counters[category]
        counter_lbl.set_value(self.stats_counts[category])

        # Unificar lenguaje visual mediante colores en los contadores
        colors = {
            "completed": "#28a745",  # Verde
            "warnings": "#FF9800",   # Naranja
            "critical": "#F44336",   # Rojo
        }
        counter_lbl.set_color(colors.get(category, "#E0E0E0"))

    def update_service_progress(self, service: str, data: dict[str, Any]) -> None:
        """Update the progress ring and status for a service.

        Args:
            service: Service key or display name.
            data: Progress payload with 'percent', 'event', 'speed', 'eta', 'alert'.
        """
        service_widget = self.progress_widgets.get(service)
        if not service_widget:
            return
        event_type = data.get("event", "progress")
        service_widget.set_event(event_type)
        percent = data.get("percent", 0)
        service_widget.setValue(min(100, max(0, percent)))
        service_widget.setInfo(data.get("speed"), data.get("eta"))
        # Sincronizar status_text con el event_type actual (evita que se quede pegado en "Advertencia")
        status_map = {
            "error": "Error",
            "start": "Sincronizando",
            "progress": "Sincronizando",
            "waiting": "En Espera",
            "warning": "Advertencia",
        }
        new_status = status_map.get(event_type)
        if new_status:
            service_widget.set_status(new_status)

    def _send_to_log_dialog(self, service: str, message: str) -> None:
        if self.log_dialog:
            self.log_dialog.append_log(service, message)

    def get_all_managers(self) -> list[Any]:
        """Return all active service manager instances (built-in and Rclone).

        Returns:
            List of service manager objects.
        """
        result = []
        if self.config_manager.get("local_sync", {}).get("enabled", False):
            result.append(self.local_manager)
        if self.config_manager.get("gdrive", {}).get("enabled", False):
            result.append(self.gdrive_manager)
        if self.config_manager.get("onedrive", {}).get("enabled", False):
            result.append(self.onedrive_manager)
        result.extend(self.rclone_managers)
        return result

    def sync_all_managers(self) -> None:
        """Trigger a sync on every active service manager."""
        for manager in self.get_all_managers():
            manager.sync()

    def closeEvent(self, event: Any) -> None:
        """Hide the window to tray instead of closing the application."""
        event.ignore()
        self.hide()
        self.tray.show_message("Sync Master", "La aplicación sigue ejecutándose en segundo plano.")

    def shutdown_all_managers(self) -> None:
        """Gracefully stop all service managers during application shutdown."""
        for manager in self.get_all_managers():
            try:
                if hasattr(manager, "shutdown"):
                    manager.shutdown()
                elif hasattr(manager, "stop_timer"):
                    manager.stop_timer()
            except Exception:
                service_name = getattr(manager, "service_name", manager.__class__.__name__)
                self.append_log(f"{service_name}: error durante el cierre ordenado.", force=True)
