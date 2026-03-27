# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


from PyQt6.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QHBoxLayout, QFrame,
    QSystemTrayIcon, QMessageBox, QScrollArea, QSizePolicy,
    QStyle, QDialog, QCheckBox, QDialogButtonBox, QMenu, QTextEdit
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QRectF, QVariantAnimation, 
    pyqtProperty, QPropertyAnimation, QEasingCurve
)
from PyQt6.QtGui import QIcon, QPainter, QPen, QColor, QFont, QPixmap
from ui.log_dialog import LogDialog
from ui.settings_dialog import SettingsDialog


# Widget personalizado que dibuja un anillo de progreso circular para cada servicio
class CircularProgress(QWidget):
    def __init__(self, label_text, size=150, parent=None):
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
        
        # Animación nativa de color para el arco
        self.color_anim = QPropertyAnimation(self, b"arcColor")
        self.color_anim.setDuration(500)
        self.color_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    @pyqtProperty(QColor)
    def arcColor(self):
        return self._arc_color

    @arcColor.setter
    def arcColor(self, color):
        self._arc_color = QColor(color)
        # Sincronizar color del texto si no es el verde base (mejor legibilidad)
        if self._arc_color != QColor("#4CAF50"):
            self.status_color = self._arc_color
        else:
            self.status_color = QColor("#E0E0E0")
        self.update()

    def _animate_to(self, target_hex):
        if self.target_color_hex == target_hex:
            return
        self.target_color_hex = target_hex
        self.color_anim.stop()
        self.color_anim.setStartValue(self._arc_color)
        self.color_anim.setEndValue(QColor(target_hex))
        self.color_anim.start()

    def setValue(self, value):
        self.percent = max(0, min(100, value))
        self.update()

    def set_status(self, status_text):
        """Define el texto de estado y dispara la animación de color del arco."""
        self.status_text = status_text
        s = status_text.lower()
        if "error" in s or "sin conexión" in s:
            target = "#F44336"
        elif "sincronizando" in s or "escaneando" in s:
            target = "#00BFFF"
        elif "sincronizado" in s or "activo" in s:
            target = "#4CAF50" # Verde para éxito/reposo
        elif "paus" in s or "en espera" in s:
            target = "#f7e05f"
        elif "limitado" in s or "advertencia" in s:
            target = "#FF9800"
        else:
            target = "#4CAF50"
        
        self._animate_to(target)

    def set_event(self, event_type):
        """Asigna un evento rclone con transición de color suave."""
        colors = {
            "start": "#00BFFF",
            "progress": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336"
        }
        self.event_type = event_type
        target = colors.get(event_type, "#4CAF50")
        
        if event_type == "warning":
            self.event_icon = "⚠️"
        elif event_type == "error":
            self.event_icon = "🛑"
        else:
            self.event_icon = ""
            
        self._animate_to(target)

    def setInfo(self, speed, eta):
        self.speed = speed or ""
        self.eta = eta or ""
        self.update()

    def paintEvent(self, event):
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
        elif self.status_text and self.status_text.lower() not in ["", "listo", "en espera"]:
            span_val = 100 # Mostrar color completo del estado si está activo
        
        if span_val > 0:
            prog_pen = QPen(self._arc_color, 10)
            prog_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(prog_pen)
            span = int(360 * span_val / 100)
            # Dibujar desde las 12:00 (90 grados) en sentido horario
            painter.drawArc(arc_rect, 90 * 16, -span * 16)

        # 4. Texto central y alertas
        cx = rect.center().x()
        cy = rect.center().y()

        if self.event_icon:
            icon_font = QFont("Segoe UI", 16)
            icon_font.setBold(True)
            painter.setFont(icon_font)
            painter.setPen(QColor("#E0E0E0"))
            icon_rect = QRectF(cx - 30, cy - 28, 60, 24)
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, self.event_icon)

        if self.status_text:
            # Texto de estado bajo el icono (o centrado si no hay icono)
            status_font = QFont("Segoe UI", 9)
            status_font.setBold(True)
            painter.setFont(status_font)
            painter.setPen(self.status_color)
            offset_y = 6 if self.event_icon else 0
            # Aumentar el ancho a 120 para que estados como "Sincronizando" quepan
            status_rect = QRectF(cx - 60, cy - 10 + offset_y, 120, 24)
            painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, self.status_text)
        # Se elimina el renderizado del porcentaje (%) por petición del usuario
from managers.rclone_service import RcloneServiceManager, PROGRESS_PATTERN, SPEED_PATTERN, ETA_PATTERN
import os
import time
import shutil
import re

# Ventana principal de la app (gestiona la UI, tarjetas de sincronización y métricas)
class MainWindow(QMainWindow):
    MODE_ICONS = {
        "bisync": "↔",
        "copy": "↑",
        "sync": "⇄"
    }
    MODE_COLORS = {
        "bisync": "#9CDCFE",
        "copy": "#8ad1ff",
        "sync": "#f0d83a"
    }
    SERVICE_BRACKET_PATTERN = re.compile(r'^\[([^\]]+)\]')
    SERVICE_PREFIX_PATTERN = re.compile(r'^([^:\[\]]+):')
    def __init__(self, config_manager, onedrive_manager, gdrive_manager, local_manager, version, tray, rclone_managers=None):
        super().__init__()
        self.config_manager = config_manager
        self.onedrive_manager = onedrive_manager
        self.gdrive_manager = gdrive_manager
        self.local_manager = local_manager
        self.version = version
        self.tray = tray
        self.rclone_managers = rclone_managers or []
        self.rclone_manager_map = {}
        self._completed_syncs = set() # {service_key: last_sync_timestamp}
        self._connected_rclone_names = set()
        self.notification_cooldown = 60
        self.last_notifications = {}
        self.display_names = {
            "local_sync": "Local (Rclone)",
            "gdrive": "Google Drive (Rclone)",
            "onedrive": "OneDrive (on-prem)"
        }
        
        self.setWindowTitle(f"Sync Master v{self.version} - Monitor en Tiempo Real")
        self.resize(1200, 720)
        self.setStyleSheet("""
            background-color: #1E1E1E;
            color: #E0E0E0;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            font-size: 13px;
        """)
        
        # Icon
        icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets/logo.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # UI Elements storage
        self.status_labels = {}
        self.interval_labels = {}
        self.last_sync_labels = {}
        self.mode_labels = {}
        self.last_statuses = {} 
        self.service_buttons = {}
        self.service_managers = {}
        self.service_pause_states = {}
        self.stats_counts = {"completed": 0, "warnings": 0, "critical": 0}
        self.card_width = 260
        self.card_height = 220
        self.card_frames = []
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
        self.progress_widgets = {}
        
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

    def setup_ui(self):
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
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(40, 40)
        self.next_btn.clicked.connect(self.scroll_next)
        self.next_btn.setStyleSheet(self.icon_button_style)
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
            "completed": self._create_counter("Archivos Completados", "0", counters_layout),
            "warnings": self._create_counter("Advertencias", "0", counters_layout),
            "critical": self._create_counter("Errores Críticos", "0", counters_layout)
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

    def show_global_menu(self):
        from PyQt6.QtCore import QPoint
        pos = self.menu_btn.mapToGlobal(QPoint(0, 0))
        menu_size = self.global_menu.sizeHint()
        # Mueve el menú hacia adentro (izquierda) y arriba, ya que el botón está en la esquina inferior
        pos.setX(pos.x() - menu_size.width() + self.menu_btn.width())
        pos.setY(pos.y() - menu_size.height())
        self.global_menu.exec(pos)

    def _create_global_menu(self):
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

    def _create_menu_icon(self):
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

    def create_service_card(self, title, key, manager):
        # Genera una tarjeta individual (box) para monitorear un servicio específico
        frame = QFrame()
        total_height = 360
        frame.setFixedSize(self.card_width, total_height)
        frame.setStyleSheet("background-color: #2D2D2D; border-radius: 12px;")
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 7, 8, 6)
        layout.setSpacing(6)
        frame.setLayout(layout)
        
        # Title
        title_lbl = QLabel(f"<b>{title}</b>")
        title_lbl.setStyleSheet("color: #9CDCFE; font-size: 16px; margin-bottom: 5px;")
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        
        # Status
        self.status_labels[key] = QLabel("Estado: Desconocido")
        self.status_labels[key].setStyleSheet("color: #E0E0E0; font-size: 13px;")
        layout.addWidget(self.status_labels[key])

        self.mode_labels[key] = QLabel("")
        self.mode_labels[key].setStyleSheet("color: #9CDCFE; font-size: 12px;")
        layout.addWidget(self.mode_labels[key])
        self.update_service_mode_label(key)
        
        # Interval
        self.interval_labels[key] = QLabel("Intervalo: --")
        self.interval_labels[key].setStyleSheet("color: #C7C7C7; font-size: 12px;")
        layout.addWidget(self.interval_labels[key])
        
        # Last Sync
        self.last_sync_labels[key] = QLabel("Última Sinc: Nunca")
        self.last_sync_labels[key].setStyleSheet("color: #C7C7C7; font-size: 12px;")
        layout.addWidget(self.last_sync_labels[key])
        
        # Manual Sync Button
        control_btn = QPushButton("Pausar")
        control_btn.setIcon(self.pause_icon)
        control_btn.setStyleSheet(self.toggle_pause_style)
        control_btn.clicked.connect(lambda _, k=key, m=manager: self.toggle_service_pause(k, m))
        control_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(control_btn)
        control_btn.setMinimumHeight(36)
        control_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.service_buttons[key] = control_btn
        self.service_managers[key] = manager
        self.service_pause_states.setdefault(key, False)
        self.update_service_button(key)

        progress_widget = CircularProgress(self.display_names.get(key, key), size=self.progress_ring_size)
        layout.addWidget(progress_widget, alignment=Qt.AlignmentFlag.AlignCenter)
        self.progress_widgets[key] = progress_widget

        return frame

    def connect_signals(self):
        # Conecta los eventos (señales) emitidos por los gestores hacia la UI
        # Local
        self.local_manager.status_changed.connect(lambda s: self.update_status("local_sync", s))
        self.local_manager.log_message.connect(self.append_log)
        self.local_manager.sync_finished.connect(lambda t: self.update_last_sync("local_sync", t))
        self.local_manager.progress_updated.connect(self.update_service_progress)

        # GDrive
        self.gdrive_manager.status_changed.connect(lambda s: self.update_status("gdrive", s))
        self.gdrive_manager.log_message.connect(self.append_log)
        self.gdrive_manager.sync_finished.connect(lambda t: self.update_last_sync("gdrive", t))
        self.gdrive_manager.progress_updated.connect(self.update_service_progress)
        
        # OneDrive
        self.onedrive_manager.status_changed.connect(lambda s: self.update_status("onedrive", s))
        self.onedrive_manager.log_message.connect(self.append_log)
        self.onedrive_manager.sync_finished.connect(lambda t: self.update_last_sync("onedrive", t))
        if hasattr(self.onedrive_manager, "progress_updated"):
            self.onedrive_manager.progress_updated.connect(self.update_service_progress)

    def connect_rclone_signals(self, manager, key):
        if manager.service_name in self._connected_rclone_names:
            return
        manager.status_changed.connect(lambda s, k=key: self.update_status(k, s))
        manager.log_message.connect(self.append_log)
        manager.sync_finished.connect(lambda t, k=key: self.update_last_sync(k, t))
        manager.progress_updated.connect(self.update_service_progress)
        self._connected_rclone_names.add(manager.service_name)

    def _populate_service_managers(self):
        """Populate service_managers dict with all managers (standard + rclone)."""
        # Standard managers
        self.service_managers["local_sync"] = self.local_manager
        self.service_managers["gdrive"] = self.gdrive_manager
        self.service_managers["onedrive"] = self.onedrive_manager
        
        # Dynamic rclone managers
        for manager in self.rclone_managers:
            key = f"rclone:{manager.service_name}"
            self.service_managers[key] = manager

    def build_service_cards(self):
        # Limpia y reconstruye dinámicamente todas las tarjetas de servicio según la configuración
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        self.status_labels = {}
        self.interval_labels = {}
        self.last_sync_labels = {}

        entries = [
            ("local_sync", "Local (Rclone)", self.local_manager),
            ("gdrive", "Google Drive (Rclone)", self.gdrive_manager),
            ("onedrive", "OneDrive (on-prem)", self.onedrive_manager),
        ]

        for manager in self.rclone_managers:
            key = f"rclone:{manager.service_name}"
            entries.append((key, manager.service_name, manager))
            self.display_names[key] = manager.service_name

        self.card_frames.clear()
        self.progress_widgets.clear()
        for idx, (key, title, manager) in enumerate(entries):
            card = self.create_service_card(title, key, manager)
            self.cards_layout.addWidget(card)
            self.card_frames.append(card)
        self.cards_layout.addStretch()
        self.snap_scroll_to_card(0)
        self.adjust_window_size()

    def adjust_window_size(self):
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

    def snap_scroll_to_card(self, index):
        if index < 0 or not self.card_frames:
            return
        step = self.card_width + self.cards_layout.spacing()
        target = index * step
        bar = self.cards_scroll.horizontalScrollBar()
        bar.setValue(min(bar.maximum(), target))

    def scroll_previous(self):
        bar = self.cards_scroll.horizontalScrollBar()
        step = self.card_width + self.cards_layout.spacing()
        bar.setValue(max(0, bar.value() - step))

    def scroll_next(self):
        bar = self.cards_scroll.horizontalScrollBar()
        step = self.card_width + self.cards_layout.spacing()
        bar.setValue(min(bar.maximum(), bar.value() + step))

    def reload_rclone_services(self, initial=False):
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

    def update_initial_info(self):
        for key in list(self.interval_labels.keys()):
            if key in ["local_sync", "gdrive", "onedrive"]:
                conf = self.config_manager.get(key, {})
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

    def update_status(self, key, status):
        # Evitar actualizaciones redundantes que reinician la animación y causan flicker
        if self.last_statuses.get(key) == status:
            return
        self.last_statuses[key] = status
        
        lbl = self.status_labels.get(key)
        status_lower = status.lower()

        # Corrección: El QLabel superior solo muestra Activo/Desactivado
        is_disabled = "desactivado" in status_lower or "detenido" in status_lower
        if lbl:
            if is_disabled:
                lbl.setText("Estado: Desactivado")
                lbl.setStyleSheet("color: #6c757d; font-weight: bold;")
            else:
                lbl.setText("Estado: Activo")
                lbl.setStyleSheet("color: #28a745; font-weight: bold;")

        progress_widget = self.progress_widgets.get(key)
        if progress_widget:
            # Mapear estados al evento del anillo (color del arco)
            if "sincronizando" in status_lower or "escaneando" in status_lower:
                progress_widget.set_event("start")
            elif "error" in status_lower or "sin conexión" in status_lower:
                progress_widget.set_event("error")
            elif "advertencia" in status_lower or "limitado" in status_lower:
                progress_widget.set_event("warning")
            elif "paus" in status_lower or "en espera" in status_lower:
                progress_widget.set_event("warning")
            else:
                progress_widget.set_event("progress")

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

    def update_service_mode_label(self, key):
        lbl = self.mode_labels.get(key)
        if not lbl:
            return
        mode = self.get_service_mode(key)
        icon = self.MODE_ICONS.get(mode, "↔")
        color = self.MODE_COLORS.get(mode, "#9CDCFE")
        lbl.setText(f"Modo: {mode.capitalize()} {icon}")
        lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 600;")

    def get_service_mode(self, key):
        if key in ["local_sync", "gdrive", "onedrive"]:
            conf = self.config_manager.get(key, {})
            return conf.get("mode", "bisync")
        if key.startswith("rclone:"):
            service_name = key.split(":", 1)[1]
            conf = self.get_rclone_service_config(service_name) or {}
            return conf.get("mode", "bisync")
        return "bisync"

    def update_last_sync(self, key, timestamp):
        lbl = self.last_sync_labels.get(key)
        if lbl:
            from datetime import datetime
            dt = datetime.fromtimestamp(timestamp)
            time_str = dt.strftime("%H:%M:%S")
            lbl.setText(f"Última Sinc: {time_str}")
            # Al terminar con éxito, permitimos que el próximo 100% vuelva a contar como completado
            if key in self._completed_syncs:
                self._completed_syncs.remove(key)

    def append_log(self, message, *, force=False):
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

    def should_display_log(self, message):
        # Verifica palabras clave permitidas o prohibidas para evitar spam en el historial del servicio
        lower = message.lower()
        noise_terms = [
            "modtime", "hashtype", "hash-type", "hash type", "building path", "no changes found",
            "updating listings", "scanning", "metadata", "checking", "path finished"
        ]
        if any(term in lower for term in noise_terms):
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

        if "[od]" in lower or "[od info/err]" in lower or "[od prompt]" in lower or "[od prompt stderr]" in lower:
            return True

        if self.is_error_message(message):
            return True

        return False

    def _update_progress_from_message(self, service_label, text):
        payload = self._parse_progress_payload(text)
        if not payload:
            return
        key = self._resolve_progress_key(service_label)
        if key:
            self.update_service_progress(key, payload)

    def _parse_progress_payload(self, text):
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

    def _resolve_progress_key(self, label):
        label_lower = (label or "").lower()
        if "local" in label_lower:
            return "local_sync"
        if "gdrive" in label_lower:
            return "gdrive"
        if "onedrive" in label_lower or "od" == label_lower:
            return "onedrive"
        for key, display in self.display_names.items():
            if not display:
                continue
            display_lower = display.lower()
            if label_lower == display_lower or label_lower in display_lower:
                return key
        return None

    def is_error_message(self, message):
        lower = message.lower()
        return any(term in lower for term in ["error", "failed", "critico", "critical", "sin conexión", "panic"])

    def extract_service_name(self, message):
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
                return "Local (Rclone)"
            if name_lower == "gdrive":
                return "Google Drive (Rclone)"
            if name_lower == "od" or name_lower == "onedrive":
                return "OneDrive (on-prem)"
            
            for key, display in self.display_names.items():
                if display and name_lower == display.lower():
                    return display
                    
            return name
        return self.general_standby_name

    def open_settings(self):
        dialog = SettingsDialog(self.config_manager, self)
        if dialog.exec():
            # Refresh info and restart timers
            self.reload_rclone_services()
            self.update_initial_info()
            self.onedrive_manager.start_timer()
            self.gdrive_manager.start_timer()
            self.local_manager.start_timer()
            for manager in self.rclone_managers:
                manager.start_timer()

    def clean_rclone_cache(self):
        selected_services = self._select_cache_services()
        if selected_services is None:
            return
        if not selected_services:
            QMessageBox.warning(self, "Sin servicios", "Selecciona al menos un servicio configurado.")
            return

        cache_dir = os.path.expanduser("~/.cache/rclone/bisync")
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

    def _select_cache_services(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Limpiar Caché RClone")
        layout = QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Selecciona los servicios cuya caché deseas limpiar:"))

        service_map = [
            ("Local", self.local_manager),
            ("GDrive", self.gdrive_manager),
            ("OneDrive", self.onedrive_manager),
            ("Mega-Dev", self.rclone_manager_map.get("Mega-Dev"))
        ]

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

    def _force_resync_service(self, manager, label):
        if hasattr(manager, "force_resync"):
            manager.force_resync()
            self.append_log(f"{label}: Re-sincronización inmediata iniciada.", force=True)
        else:
            self.append_log(f"{label}: No se puede iniciar re-sincronización inmediata.", force=True)

    def _schedule_resync_service(self, manager, label):
        if hasattr(manager, "force_resync_next"):
            manager.force_resync_next = True
            self.append_log(f"{label}: --resync programado para la próxima ejecución automática.", force=True)
        else:
            self.append_log(f"{label}: No se puede programar --resync automáticamente.", force=True)

    def toggle_service_pause(self, key, manager):
        if self.service_pause_states.get(key, False):
            self.resume_service(key, manager)
        else:
            self.pause_service(key, manager)

    def pause_service(self, key, manager):
        self.service_pause_states[key] = True
        manager.stop_timer()
        self.update_service_button(key)
        self.update_status(key, "Pausado")

    def resume_service(self, key, manager):
        self.service_pause_states[key] = False
        manager.start_timer()
        self.update_service_button(key)
        self.update_status(key, "Activo")

    def update_service_button(self, key):
        btn = self.service_buttons.get(key)
        if not btn:
            return
        if self.service_pause_states.get(key, False):
            btn.setText("Reanudar")
            btn.setStyleSheet(self.toggle_paused_style)
            btn.setIcon(self.play_icon)
        else:
            btn.setText("Pausar")
            btn.setStyleSheet(self.toggle_pause_style)
            btn.setIcon(self.pause_icon)

    def sync_ready_services(self):
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

    def show_log_dialog(self):
        self.log_dialog.show()

    def show_welcome_if_needed(self):
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

    def show_info(self):
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

    def get_rclone_service_config(self, service_name):
        services = self.config_manager.get("rclone_services", []) or []
        for service in services:
            if service.get("name") == service_name:
                return service
        return None

    def maybe_notify_status(self, key, status):
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

    def maybe_notify_log(self, message):
        if not self.tray:
            return

        msg_lower = message.lower()
        if "re-sincronización" in msg_lower or "resync" in msg_lower:
            self.send_notification("warning", "Sync Master", message, "warning:log")
        elif "error crítico" in msg_lower or "critico" in msg_lower:
            self.send_notification("critical", "Sync Master", message, "critical:log")

    def send_notification(self, level, title, message, dedupe_key=None):
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

    def is_service_enabled(self, key):
        if key in ["local_sync", "gdrive", "onedrive"]:
            conf = self.config_manager.get(key, {})
            return conf.get("enabled", False)
        if key.startswith("rclone:"):
            service_name = key.split(":", 1)[1]
            conf = self.get_rclone_service_config(service_name) or {}
            return conf.get("enabled", True)
        return True

    def _create_counter(self, title, value, layout):
        widget = QWidget()
        vbox = QVBoxLayout()
        vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setLayout(vbox)
        label = QLabel(title)
        label.setStyleSheet("color: #B5B5B5; font-size: 11px;")
        counter = QLabel(value)
        counter.setStyleSheet("color: #E0E0E0; font-size: 20px; font-weight: 600;")
        vbox.addWidget(label)
        vbox.addWidget(counter)
        layout.addWidget(widget)
        return counter

    def update_service_progress(self, service, data):
        service_widget = self.progress_widgets.get(service)
        if not service_widget:
            return
        event_type = data.get("event", "progress")
        service_widget.set_event(event_type)
        percent = data.get("percent", 0)
        service_widget.setValue(min(100, max(0, percent)))
        service_widget.setInfo(data.get("speed"), data.get("eta"))
        alert = data.get("alert")
        if alert or event_type == "error":
            self._update_counter("critical")
        elif event_type == "warning":
            self._update_counter("warnings")
        elif percent == 100:
            # Solo incrementar el contador si es un nuevo evento de completado (evita duplicados por polling)
            if service not in self._completed_syncs:
                self._update_counter("completed")
                self._completed_syncs.add(service)

    def _update_counter(self, key):
        if key not in self.stats_counts:
            return
        self.stats_counts[key] += 1
        counter_lbl = self.stats_counters[key]
        counter_lbl.setText(str(self.stats_counts[key]))
        
        # Unificar lenguaje visual mediante colores en los contadores
        colors = {
            "completed": "#28a745", # Verde
            "warnings": "#FF9800",  # Naranja
            "critical": "#F44336"   # Rojo
        }
        color = colors.get(key, "#E0E0E0")
        counter_lbl.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 600;")

    def _send_to_log_dialog(self, service, message):
        if self.log_dialog:
            self.log_dialog.append_log(service, message)
