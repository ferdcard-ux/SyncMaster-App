# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


import uuid

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.exclusion_presets import get_default_exclusions
from ui.client_id_dialog import ClientIdAssistantDialog
from ui.rclone_service_dialog import RcloneConfigTerminalDialog, RcloneServiceDialog


class SettingsDialog(QDialog):
    MODE_OPTIONS = [
        ("bisync", "Modo Espejo bidireccional: historia y conflictos gestionados por rclone bisync."),
        ("copy", "Modo Respaldo (copy): solo sube local → nube sin borrar en el destino."),
        ("sync", "Modo Espejo unidireccional (sync): la nube refleja exactamente la carpeta local."),
    ]

    def __init__(self, config_manager, parent=None):
        """Initialize the settings dialog.

        Args:
            config_manager: Application configuration manager instance.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.rclone_services = []
        self.local_services = []
        self.service_forms = {}
        self.local_form_widgets = {}
        self.od_form_widgets = {}
        self.gd_form_widgets = {}

        self.setWindowTitle("Configuración - Sync Master")
        self.setMinimumSize(640, 480)
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.resize(min(900, geo.width() - 40), min(600, geo.height() - 60))
        else:
            self.resize(900, 600)
        self.setStyleSheet(
            "QWidget { background-color: #1E1E1E; color: #E0E0E0; font-size: 13px; }"
            "QPushButton { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #3C3C3C; border-radius: 5px; padding: 6px 12px; text-align: center; font-size: 13px; }"
            "QPushButton:hover { background-color: #383838; border-color: #4CAF50; }"
            "QPushButton:focus-visible { outline: none; border: 1px solid #4CAF50; }"
            "QPushButton:pressed { background-color: #1E1E1E; }"
            "QDialogButtonBox QPushButton { min-width: 90px; }"
            "QTabBar::tab { min-height: 28px; padding: 8px 12px; background-color: #2D2D2D; border: 1px solid #3C3C3C; border-bottom: none; }"
            "QTabBar::tab:hover { border-color: #4CAF50; }"
            "QTabBar::tab:selected { background-color: #3C3C3C; border: 1px solid #4CAF50; border-bottom: none; }"
            "QTabBar::tab:focus { border: 1px solid #4CAF50; }"
            "QListWidget { background-color: #181818; border: 1px solid #2D2D2D; }"
            "QListWidget::item { padding: 8px; }"
            "QListWidget::item:selected { background-color: #3C3C3C; border-left: 3px solid #4CAF50; }"
            "QHeaderView::section { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #3C3C3C; padding: 4px; }"
            "QToolTip { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #4CAF50; padding: 4px; font-size: 12px; }"
        )
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """Build the tabbed layout with Services, Add Services, and General tabs."""
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        self.tab_services = QWidget()
        self.setup_services_tab()
        self.tabs.addTab(self.tab_services, "Servicios")

        self.tab_add_services = QWidget()
        self.setup_add_services_tab()
        self.tabs.addTab(self.tab_add_services, "Agregar Servicios")

        self.tab_general = QWidget()
        self.setup_general_tab()
        self.tabs.addTab(self.tab_general, "General")

        main_layout.addWidget(self.tabs)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def setup_services_tab(self):
        """Create the Services tab with a list panel and stacked detail forms."""
        layout = QHBoxLayout(self.tab_services)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        self.service_list = QListWidget()
        self.service_list.setMinimumWidth(220)
        self.service_list.currentRowChanged.connect(self.on_service_selected)
        layout.addWidget(self.service_list)

        self.service_stack = QStackedWidget()
        layout.addWidget(self.service_stack, 1)

    def setup_add_services_tab(self):
        """Create the Add Services tab with RClone and Local service admin panels."""
        layout = QVBoxLayout(self.tab_add_services)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel("Tipo de servicio:"))
        self.add_service_selector = QComboBox()
        self.add_service_selector.addItems(["Servicios RClone", "Servicio Local"])
        self.add_service_selector.currentIndexChanged.connect(self.on_add_service_type_changed)
        selector_row.addWidget(self.add_service_selector, 1)
        layout.addLayout(selector_row)

        self.add_service_stack = QStackedWidget()
        self.add_service_stack.addWidget(self._build_rclone_admin_panel())
        self.add_service_stack.addWidget(self._build_local_admin_panel())
        layout.addWidget(self.add_service_stack)

    def setup_general_tab(self):
        """Create the General tab with the autostart checkbox."""
        layout = QFormLayout(self.tab_general)
        self.autostart_checkbox = QCheckBox("Iniciar automáticamente al arrancar el sistema")
        layout.addRow(self.autostart_checkbox)

    def _build_rclone_admin_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        info = QLabel("Administra los servicios RClone registrados y usa el asistente actual para añadir nuevos.")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.rclone_table = QTableWidget(0, 3)
        self.rclone_table.setHorizontalHeaderLabels(["Nombre", "Proveedor", "Directorio Local"])
        self.rclone_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rclone_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rclone_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.rclone_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Añadir Servicio")
        add_btn.clicked.connect(self.add_rclone_service)
        remove_btn = QPushButton("Eliminar Seleccionado")
        remove_btn.clicked.connect(self.remove_rclone_service)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return panel

    def _build_local_admin_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)

        info = QLabel(
            "Crea servicios locales adicionales con la misma lógica del servicio local principal. "
            "Una vez añadidos, aparecerán también en la pestaña Servicios."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.local_services_table = QTableWidget(0, 3)
        self.local_services_table.setHorizontalHeaderLabels(["Nombre", "Directorio A", "Directorio B"])
        self.local_services_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.local_services_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.local_services_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.local_services_table)

        remove_row = QHBoxLayout()
        remove_btn = QPushButton("Eliminar Servicio Local Seleccionado")
        remove_btn.clicked.connect(self.remove_local_service)
        remove_row.addWidget(remove_btn)
        remove_row.addStretch()
        layout.addLayout(remove_row)

        add_group = QGroupBox("Nuevo Servicio Local")
        add_layout = QFormLayout(add_group)

        self.new_local_name = QLineEdit()
        self.new_local_name.setPlaceholderText("Ej. Proyectos, Backups, Documentos")
        add_layout.addRow("Nombre:", self.new_local_name)

        self.new_local_enabled = QCheckBox("Habilitar este servicio local")
        self.new_local_enabled.setChecked(True)
        add_layout.addRow(self.new_local_enabled)

        self.new_local_dir_a = QLineEdit()
        btn_a = QPushButton("Explorar (A)")
        btn_a.clicked.connect(lambda: self.browse_folder(self.new_local_dir_a))
        row_a = QHBoxLayout()
        row_a.addWidget(self.new_local_dir_a)
        row_a.addWidget(btn_a)
        add_layout.addRow("Directorio A:", row_a)

        self.new_local_dir_b = QLineEdit()
        btn_b = QPushButton("Explorar (B)")
        btn_b.clicked.connect(lambda: self.browse_folder(self.new_local_dir_b))
        row_b = QHBoxLayout()
        row_b.addWidget(self.new_local_dir_b)
        row_b.addWidget(btn_b)
        add_layout.addRow("Directorio B:", row_b)

        self.new_local_interval = QSpinBox()
        self.new_local_interval.setRange(1, 1440)
        self.new_local_interval.setSuffix(" min")
        self.new_local_interval.setValue(15)
        add_layout.addRow("Intervalo:", self.new_local_interval)

        self.new_local_exclusions = QPlainTextEdit()
        self.new_local_exclusions.setPlaceholderText("Ejemplos:\nName *.log\nPath temp/*\nName .git")
        add_layout.addRow("Exclusiones:", self.new_local_exclusions)

        self.new_local_mode = self.create_mode_combo()
        add_layout.addRow("Modo de sincronización:", self.new_local_mode)

        add_btn = QPushButton("Añadir Servicio Local")
        add_btn.clicked.connect(self.add_local_service)
        add_layout.addRow(add_btn)

        layout.addWidget(add_group)
        return panel

    def on_add_service_type_changed(self, index):
        """Switch the add-service panel when the service type selector changes.

        Args:
            index: Index of the newly selected service type.
        """
        self.add_service_stack.setCurrentIndex(index)

    def create_mode_combo(self):
        """Create a styled combo box populated with sync mode options.

        Returns:
            QComboBox with bisync/copy/sync entries and tooltips.
        """
        combo = QComboBox()
        combo.setStyleSheet(
            "QComboBox { background-color: #2D2D2D; color: #E0E0E0; border: 1px solid #3C3C3C; border-radius: 4px; padding: 4px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1E1E1E; selection-background-color: #3C3C3C; }"
        )
        for idx, (key, desc) in enumerate(self.MODE_OPTIONS):
            combo.addItem(key, key)
            combo.setItemData(idx, desc, Qt.ItemDataRole.ToolTipRole)
        combo.currentIndexChanged.connect(lambda idx, c=combo: self.update_mode_tooltip(c, idx))
        self.update_mode_tooltip(combo, combo.currentIndex())
        return combo

    def update_mode_tooltip(self, combo, index):
        """Update the tooltip of a mode combo box to match the selected item.

        Args:
            combo: The QComboBox to update.
            index: Currently selected index.
        """
        desc = combo.itemData(index, Qt.ItemDataRole.ToolTipRole)
        if desc:
            combo.setToolTip(desc)

    def set_mode_combo(self, combo, value):
        """Select a mode value in a combo box, falling back to 'bisync'.

        Args:
            combo: The QComboBox to set.
            value: The mode data value to select.
        """
        idx = combo.findData(value)
        if idx == -1:
            idx = combo.findText("bisync")
        if idx != -1:
            combo.setCurrentIndex(idx)

    def browse_folder(self, line_edit):
        """Open a folder selection dialog and set the result in the given line edit.

        Args:
            line_edit: QLineEdit to populate with the selected path.
        """
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder:
            line_edit.setText(folder)

    def _create_panel_scroll(self, inner_widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(inner_widget)
        return scroll

    def _create_local_form(self, title, checkbox_text):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        group = QGroupBox(title)
        form = QFormLayout(group)

        enabled = QCheckBox(checkbox_text)
        form.addRow(enabled)

        local_dir_a = QLineEdit()
        btn_a = QPushButton("Explorar (A)")
        btn_a.clicked.connect(lambda: self.browse_folder(local_dir_a))
        row_a = QHBoxLayout()
        row_a.addWidget(local_dir_a)
        row_a.addWidget(btn_a)
        form.addRow("Directorio A:", row_a)

        local_dir_b = QLineEdit()
        btn_b = QPushButton("Explorar (B)")
        btn_b.clicked.connect(lambda: self.browse_folder(local_dir_b))
        row_b = QHBoxLayout()
        row_b.addWidget(local_dir_b)
        row_b.addWidget(btn_b)
        form.addRow("Directorio B:", row_b)

        interval = QSpinBox()
        interval.setRange(1, 1440)
        interval.setSuffix(" min")
        form.addRow("Intervalo:", interval)

        exclusions = QPlainTextEdit()
        exclusions.setPlaceholderText("Ejemplos:\nName *.log\nPath temp/*\nName .git")
        exclusions.setToolTip("Un patrón por línea. Use 'Name' para archivos o 'Path' para rutas relativas.")
        form.addRow("Exclusiones:", exclusions)

        mode = self.create_mode_combo()
        form.addRow("Modo de sincronización:", mode)

        layout.addWidget(group)
        layout.addStretch()
        widgets = {
            "enabled": enabled,
            "local_dir_a": local_dir_a,
            "local_dir_b": local_dir_b,
            "interval_minutes": interval,
            "exclusions": exclusions,
            "mode": mode,
        }
        return panel, widgets

    def _create_onedrive_form(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        group = QGroupBox("OneDrive")
        form = QFormLayout(group)

        enabled = QCheckBox("Habilitar OneDrive")
        form.addRow(enabled)

        local_path = QLineEdit()
        local_btn = QPushButton("Explorar")
        local_btn.clicked.connect(lambda: self.browse_folder(local_path))
        local_row = QHBoxLayout()
        local_row.addWidget(local_path)
        local_row.addWidget(local_btn)
        form.addRow("Directorio Local:", local_row)

        remote_path = QLineEdit()
        remote_path.setPlaceholderText("NombreRemoto:Ruta (ej. OneDrive:/)")
        form.addRow("Directorio Remoto:", remote_path)

        rclone_btn = QPushButton("Configurar RClone (OneDrive)")
        rclone_btn.clicked.connect(lambda: self._setup_rclone_for("onedrive", remote_path))
        form.addRow(rclone_btn)

        clientid_btn = QPushButton("Usar tu propio Client ID (reconectar)")
        clientid_btn.clicked.connect(
            lambda: self._open_client_id_assistant("onedrive", remote_path.text())
        )
        form.addRow(clientid_btn)

        interval = QSpinBox()
        interval.setRange(1, 1440)
        interval.setSuffix(" min")
        form.addRow("Intervalo:", interval)

        exclusions = QPlainTextEdit()
        exclusions.setPlaceholderText("Ejemplos:\n*.tmp\nnode_modules/\n~*")
        form.addRow("Exclusiones:", exclusions)

        mode = self.create_mode_combo()
        form.addRow("Modo de sincronización:", mode)

        layout.addWidget(group)
        layout.addStretch()
        widgets = {
            "enabled": enabled,
            "local_dir": local_path,
            "remote_dir": remote_path,
            "interval_minutes": interval,
            "exclusions": exclusions,
            "mode": mode,
        }
        return panel, widgets

    def _create_gdrive_form(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        group = QGroupBox("Google Drive")
        form = QFormLayout(group)

        enabled = QCheckBox("Habilitar Google Drive")
        form.addRow(enabled)

        local_path = QLineEdit()
        local_btn = QPushButton("Explorar")
        local_btn.clicked.connect(lambda: self.browse_folder(local_path))
        local_row = QHBoxLayout()
        local_row.addWidget(local_path)
        local_row.addWidget(local_btn)
        form.addRow("Directorio Local:", local_row)

        remote_path = QLineEdit()
        remote_path.setPlaceholderText("NombreRemoto:Ruta (ej. GoogleDrive:/)")
        form.addRow("Directorio Remoto:", remote_path)

        rclone_btn = QPushButton("Configurar RClone (Google Drive)")
        rclone_btn.clicked.connect(lambda: self._setup_rclone_for("gdrive", remote_path))
        form.addRow(rclone_btn)

        clientid_btn = QPushButton("Usar tu propio Client ID (reconectar)")
        clientid_btn.clicked.connect(
            lambda: self._open_client_id_assistant("gdrive", remote_path.text())
        )
        form.addRow(clientid_btn)

        interval = QSpinBox()
        interval.setRange(1, 1440)
        interval.setSuffix(" min")
        form.addRow("Intervalo:", interval)

        exclusions = QPlainTextEdit()
        exclusions.setPlaceholderText("Ejemplos:\n*.bak\nnode_modules/**\nsecret.key")
        form.addRow("Exclusiones:", exclusions)

        mode = self.create_mode_combo()
        form.addRow("Modo de sincronización:", mode)

        layout.addWidget(group)
        layout.addStretch()
        widgets = {
            "enabled": enabled,
            "local_dir": local_path,
            "remote_dir": remote_path,
            "interval_minutes": interval,
            "exclusions": exclusions,
            "mode": mode,
        }
        return panel, widgets

    def _setup_rclone_for(self, service_type, remote_path_edit):
        provider_map = {"gdrive": "drive", "onedrive": "onedrive"}
        name_map = {"gdrive": "GoogleDrive", "onedrive": "onedrive"}
        provider = provider_map.get(service_type, "")
        suggested_name = name_map.get(service_type, "")

        from ui.rclone_service_dialog import RcloneServiceDialog
        dialog = RcloneServiceDialog(self, provider_hint=provider, name_hint=suggested_name)
        if dialog.exec():
            service = dialog.get_service()
            name = service.get("name", suggested_name)
            remote_path_edit.setText(f"{name}:/")

    def _open_client_id_assistant(self, provider: str, remote_dir: str) -> None:
        """Open the custom Client ID assistant for the given remote.

        Args:
            provider: Backend provider string (e.g. 'gdrive', 'onedrive', 'drive').
            remote_dir: Remote directory string, e.g. 'GoogleDrive:/'.
        """
        remote = ""
        if remote_dir:
            remote = remote_dir.split(":")[0].strip()
        if not remote:
            QMessageBox.information(
                self,
                "Client ID propio",
                "Primero configura el remoto rclone (botón 'Configurar RClone') y vuelve a intentarlo.",
            )
            return
        assistant = ClientIdAssistantDialog(self, preset_remote=remote)
        assistant.exec()

    def _create_rclone_form(self, service):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        group = QGroupBox(service.get("name", "Servicio RClone"))
        form = QFormLayout(group)

        enabled = QCheckBox(f"Habilitar {service.get('name', 'Servicio')}")
        form.addRow(enabled)

        local_path = QLineEdit()
        local_btn = QPushButton("Explorar")
        local_btn.clicked.connect(lambda: self.browse_folder(local_path))
        local_row = QHBoxLayout()
        local_row.addWidget(local_path)
        local_row.addWidget(local_btn)
        form.addRow("Directorio Local:", local_row)

        remote_path = QLineEdit()
        remote_path.setPlaceholderText(f"{service.get('name', 'Servicio')}:/")
        form.addRow("Directorio Remoto:", remote_path)

        clientid_btn = QPushButton("Usar tu propio Client ID (reconectar)")
        clientid_btn.clicked.connect(
            lambda: self._open_client_id_assistant(
                service.get("provider", ""), remote_path.text()
            )
        )
        form.addRow(clientid_btn)

        interval = QSpinBox()
        interval.setRange(1, 1440)
        interval.setSuffix(" min")
        form.addRow("Intervalo:", interval)

        exclusions = QPlainTextEdit()
        exclusions.setPlaceholderText("Ejemplos:\n*.tmp\nnode_modules/\n~*")
        form.addRow("Exclusiones:", exclusions)

        mode = self.create_mode_combo()
        form.addRow("Modo de sincronización:", mode)

        layout.addWidget(group)
        layout.addStretch()
        widgets = {
            "enabled": enabled,
            "local_dir": local_path,
            "remote_dir": remote_path,
            "interval_minutes": interval,
            "exclusions": exclusions,
            "mode": mode,
        }
        return panel, widgets

    def _set_local_form_values(self, widgets, conf):
        widgets["enabled"].setChecked(conf.get("enabled", False))
        widgets["local_dir_a"].setText(conf.get("local_dir_a", ""))
        widgets["local_dir_b"].setText(conf.get("local_dir_b", ""))
        widgets["interval_minutes"].setValue(conf.get("interval_minutes", 15))
        widgets["exclusions"].setPlainText(conf.get("exclusions", ""))
        self.set_mode_combo(widgets["mode"], conf.get("mode", "bisync"))

    def _set_generic_form_values(self, widgets, conf):
        widgets["enabled"].setChecked(conf.get("enabled", False))
        widgets["local_dir"].setText(conf.get("local_dir", ""))
        widgets["remote_dir"].setText(conf.get("remote_dir", ""))
        widgets["interval_minutes"].setValue(conf.get("interval_minutes", 15))
        widgets["exclusions"].setPlainText(conf.get("exclusions", ""))
        self.set_mode_combo(widgets["mode"], conf.get("mode", "bisync"))

    def _local_form_payload(self, widgets):
        return {
            "enabled": widgets["enabled"].isChecked(),
            "local_dir_a": widgets["local_dir_a"].text(),
            "local_dir_b": widgets["local_dir_b"].text(),
            "interval_minutes": widgets["interval_minutes"].value(),
            "exclusions": widgets["exclusions"].toPlainText(),
            "mode": widgets["mode"].currentText(),
        }

    def _generic_form_payload(self, widgets):
        return {
            "enabled": widgets["enabled"].isChecked(),
            "local_dir": widgets["local_dir"].text(),
            "remote_dir": widgets["remote_dir"].text(),
            "interval_minutes": widgets["interval_minutes"].value(),
            "exclusions": widgets["exclusions"].toPlainText(),
            "mode": widgets["mode"].currentText(),
        }

    def load_settings(self):
        """Load all configuration values into the dialog form fields."""
        gen_conf = self.config_manager.get("general", {})
        self.autostart_checkbox.setChecked(gen_conf.get("autostart", False))

        self.rclone_services = list(self.config_manager.get("rclone_services", []) or [])
        self.local_services = list(self.config_manager.get("local_services", []) or [])
        for service in self.local_services:
            service.setdefault("id", uuid.uuid4().hex[:12])

        self.refresh_service_views(selected_key="local_sync")
        self.refresh_rclone_table()
        self.refresh_local_services_table()

    def refresh_service_views(self, selected_key=None):
        """Rebuild the service list and stacked forms from current config state.

        Args:
            selected_key: Service key to select after rebuilding, or None for default.
        """
        preserved = self.capture_service_form_state()

        self.service_forms = {}
        self.service_list.clear()
        while self.service_stack.count():
            widget = self.service_stack.widget(0)
            self.service_stack.removeWidget(widget)
            widget.deleteLater()

        local_state = preserved.get("local_sync", self.config_manager.get("local_sync", {}))
        local_panel, self.local_form_widgets = self._create_local_form(
            "Servicio Local Principal", "Habilitar Sincronización Local"
        )
        self._set_local_form_values(self.local_form_widgets, local_state)
        self._register_service_panel("local_sync", "Local (Rclone)", local_panel, self.local_form_widgets, "local")

        gdrive_state = preserved.get("gdrive", self.config_manager.get("gdrive", {}))
        gdrive_panel, self.gd_form_widgets = self._create_gdrive_form()
        self._set_generic_form_values(self.gd_form_widgets, gdrive_state)
        self._register_service_panel("gdrive", "Google Drive", gdrive_panel, self.gd_form_widgets, "gdrive")

        onedrive_state = preserved.get("onedrive", self.config_manager.get("onedrive", {}))
        onedrive_panel, self.od_form_widgets = self._create_onedrive_form()
        self._set_generic_form_values(self.od_form_widgets, onedrive_state)
        self._register_service_panel("onedrive", "OneDrive", onedrive_panel, self.od_form_widgets, "onedrive")

        for service in self.local_services:
            key = f"local:{service.get('id')}"
            panel, widgets = self._create_local_form(
                f"Servicio Local: {service.get('name', 'Local')}",
                f"Habilitar {service.get('name', 'Servicio Local')}",
            )
            self._set_local_form_values(widgets, service)
            self._register_service_panel(key, service.get("name", "Servicio Local"), panel, widgets, "local_dynamic")

        for service in self.rclone_services:
            key = f"rclone:{service.get('name', '')}"
            panel, widgets = self._create_rclone_form(service)
            self._set_generic_form_values(widgets, service)
            self._register_service_panel(key, service.get("name", "Servicio RClone"), panel, widgets, "rclone")

        if self.service_list.count():
            target_row = 0
            if selected_key:
                for row in range(self.service_list.count()):
                    item = self.service_list.item(row)
                    if item.data(Qt.ItemDataRole.UserRole) == selected_key:
                        target_row = row
                        break
            self.service_list.setCurrentRow(target_row)

    def _register_service_panel(self, key, label, panel, widgets, kind):
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.service_list.addItem(item)
        self.service_stack.addWidget(self._create_panel_scroll(panel))
        self.service_forms[key] = {"widgets": widgets, "kind": kind}

    def capture_service_form_state(self):
        """Snapshot the current values of all service form widgets.

        Returns:
            Dict mapping service keys to their current form payloads.
        """
        state = {}
        if self.service_forms:
            for key, entry in self.service_forms.items():
                widgets = entry["widgets"]
                kind = entry["kind"]
                if kind in {"local", "local_dynamic"}:
                    state[key] = self._local_form_payload(widgets)
                else:
                    state[key] = self._generic_form_payload(widgets)
        return state

    def on_service_selected(self, row):
        """Show the stacked form for the selected service.

        Args:
            row: Row index in the service list.
        """
        if row < 0:
            return
        self.service_stack.setCurrentIndex(row)

    def save_settings(self):
        """Persist all form values to the config manager and close the dialog."""
        try:
            self.apply_service_form_edits()

            autostart_enabled = self.autostart_checkbox.isChecked()
            current_general = self.config_manager.get("general", {})
            current_general["autostart"] = autostart_enabled
            self.config_manager.set("general", current_general)

            from managers.autostart import AutostartManager

            AutostartManager().set_enabled(autostart_enabled)

            self.config_manager.set("local_sync", self._local_form_payload(self.local_form_widgets))
            self.config_manager.set("onedrive", self._generic_form_payload(self.od_form_widgets))

            current_gd = self.config_manager.get("gdrive", {})
            gd_payload = self._generic_form_payload(self.gd_form_widgets)
            gd_payload["auto_dedupe"] = current_gd.get("auto_dedupe", True)
            self.config_manager.set("gdrive", gd_payload)

            self.config_manager.set("local_services", self.local_services)
            self.config_manager.set("rclone_services", self.rclone_services)
            self.accept()
            self._verify_services_after_save()
        except Exception as e:
            import logging
            logging.exception("Error al guardar configuración")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Ocurrió un error al guardar la configuración:\n{e}")

    def _verify_services_after_save(self):
        from managers.rclone_service import RcloneServiceManager as RSM
        failed = []
        for svc in self.rclone_services:
            name = svc.get("name", "")
            remote_dir = svc.get("remote_dir", "").rstrip(":")
            ok, msg = RSM.verify_remote(remote_dir)
            if not ok:
                failed.append((name, msg))
        if failed:
            from PyQt6.QtWidgets import QMessageBox
            lines = "\n".join(f"• {name}: {msg}" for name, msg in failed)
            QMessageBox.warning(
                self, "Error de credenciales",
                f"Los siguientes servicios tienen problemas de autenticación:\n\n{lines}\n\n"
                "Verifica las credenciales en la configuración de rclone o reconecta la cuenta."
            )

    def apply_service_form_edits(self):
        """Write current form widget values back into the in-memory service lists."""
        for key, entry in self.service_forms.items():
            widgets = entry["widgets"]
            kind = entry["kind"]
            if kind == "local_dynamic":
                service_id = key.split(":", 1)[1]
                for service in self.local_services:
                    if service.get("id") == service_id:
                        service.update(self._local_form_payload(widgets))
                        break
            elif kind == "rclone":
                service_name = key.split(":", 1)[1]
                for service in self.rclone_services:
                    if service.get("name") == service_name:
                        service.update(self._generic_form_payload(widgets))
                        break

    def refresh_rclone_table(self):
        """Repopulate the RClone services table from the in-memory list."""
        self.rclone_table.setRowCount(0)
        for service in self.rclone_services:
            row = self.rclone_table.rowCount()
            self.rclone_table.insertRow(row)
            self.rclone_table.setItem(row, 0, QTableWidgetItem(service.get("name", "")))
            self.rclone_table.setItem(row, 1, QTableWidgetItem(service.get("provider", "")))
            self.rclone_table.setItem(row, 2, QTableWidgetItem(service.get("local_dir", "")))

    def refresh_local_services_table(self):
        """Repopulate the local services table from the in-memory list."""
        self.local_services_table.setRowCount(0)
        for service in self.local_services:
            row = self.local_services_table.rowCount()
            self.local_services_table.insertRow(row)
            self.local_services_table.setItem(row, 0, QTableWidgetItem(service.get("name", "")))
            self.local_services_table.setItem(row, 1, QTableWidgetItem(service.get("local_dir_a", "")))
            self.local_services_table.setItem(row, 2, QTableWidgetItem(service.get("local_dir_b", "")))

    def add_rclone_service(self):
        """Open the Rclone service dialog and add a new service if confirmed."""
        self.apply_service_form_edits()
        dialog = RcloneServiceDialog(self)
        if dialog.exec():
            service = dialog.get_service()
            if any(s.get("name", "").lower() == service.get("name", "").lower() for s in self.rclone_services):
                QMessageBox.warning(self, "Duplicado", "Ya existe un servicio con ese nombre.")
                return
            service.setdefault("remote_dir", f"{service.get('name', '').strip()}:")
            service.setdefault("interval_minutes", 15)
            service.setdefault("enabled", True)
            service.setdefault("exclusions", get_default_exclusions(service.get("provider", "")))
            service.setdefault("mode", "bisync")
            self.rclone_services.append(service)
            self.refresh_rclone_table()
            self.refresh_service_views(selected_key=f"rclone:{service.get('name', '')}")

    def remove_rclone_service(self):
        """Remove the selected RClone service(s) after user confirmation."""
        self.apply_service_form_edits()
        selected = self.rclone_table.selectionModel().selectedRows()
        if not selected:
            return
        for index in sorted([item.row() for item in selected], reverse=True):
            service = self.rclone_services[index]
            name = service.get("name", "")
            message = (
                f"Estás a punto de eliminar el servicio '{name}'.\n\n"
                "Se abrirá la terminal interactiva de rclone config para que confirmes la eliminación "
                "(selecciona 'd' y luego el servicio correspondiente)."
            )
            answer = QMessageBox.question(
                self,
                "Eliminar servicio Rclone",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                continue

            terminal = RcloneConfigTerminalDialog(
                "Eliminar Servicio Rclone",
                f"Terminal interactiva para eliminar '{name}'. Sigue el flujo de rclone config (opción 'd').",
                self,
            )
            terminal.exec()
            del self.rclone_services[index]
        self.refresh_rclone_table()
        self.refresh_service_views(selected_key="local_sync")

    def add_local_service(self):
        """Create a new local service from the add-service form fields."""
        self.apply_service_form_edits()
        name = self.new_local_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Nombre requerido", "Debes indicar un nombre para el servicio local.")
            return
        if any(service.get("name", "").lower() == name.lower() for service in self.local_services):
            QMessageBox.warning(self, "Duplicado", "Ya existe un servicio local con ese nombre.")
            return

        service = {
            "id": uuid.uuid4().hex[:12],
            "name": name,
            "enabled": self.new_local_enabled.isChecked(),
            "local_dir_a": self.new_local_dir_a.text(),
            "local_dir_b": self.new_local_dir_b.text(),
            "interval_minutes": self.new_local_interval.value(),
            "exclusions": self.new_local_exclusions.toPlainText(),
            "mode": self.new_local_mode.currentText(),
        }
        self.local_services.append(service)
        self.refresh_local_services_table()
        self.refresh_service_views(selected_key=f"local:{service['id']}")
        self._reset_new_local_form()

    def _reset_new_local_form(self):
        self.new_local_name.clear()
        self.new_local_enabled.setChecked(True)
        self.new_local_dir_a.clear()
        self.new_local_dir_b.clear()
        self.new_local_interval.setValue(15)
        self.new_local_exclusions.clear()
        self.set_mode_combo(self.new_local_mode, "bisync")

    def remove_local_service(self):
        """Remove the selected local service(s) after user confirmation."""
        self.apply_service_form_edits()
        selected = self.local_services_table.selectionModel().selectedRows()
        if not selected:
            return
        for index in sorted([item.row() for item in selected], reverse=True):
            service = self.local_services[index]
            answer = QMessageBox.question(
                self,
                "Eliminar servicio local",
                f"¿Deseas eliminar el servicio local '{service.get('name', 'Servicio Local')}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                del self.local_services[index]
        self.refresh_local_services_table()
        self.refresh_service_views(selected_key="local_sync")
