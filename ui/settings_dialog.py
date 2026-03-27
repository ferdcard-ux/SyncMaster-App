# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QCheckBox, QSpinBox,
                             QGroupBox, QFileDialog, QFormLayout, QDialogButtonBox,
                             QTabWidget, QWidget, QPlainTextEdit, QTableWidget,
                             QTableWidgetItem, QAbstractItemView, QComboBox, QMessageBox)
from PyQt6.QtCore import Qt
from ui.rclone_service_dialog import RcloneServiceDialog, RcloneConfigTerminalDialog

class SettingsDialog(QDialog):
    MODE_OPTIONS = [
        ("bisync", "Modo Espejo bidireccional: historia y conflictos gestionados por rclone bisync."),
        ("copy", "Modo Respaldo (copy): solo sube local → nube sin borrar en el destino."),
        ("sync", "Modo Espejo unidireccional (sync): la nube refleja exactamente la carpeta local.")
    ]

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.rclone_services = []
        self.rclone_service_tabs = {}
        self.setWindowTitle("Configuración - Sync Master")
        self.resize(600, 450)
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
        )
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        
        # --- Local Sync Tab ---
        self.tab_local = QWidget()
        local_layout = QFormLayout()
        local_layout.setVerticalSpacing(8)

        self.local_enabled = QCheckBox("Habilitar Sincronización Local")
        local_layout.addRow(self.local_enabled)
        
        self.local_dir_a = QLineEdit()
        self.local_btn_a = QPushButton("Explorar (A)")
        self.local_btn_a.clicked.connect(lambda: self.browse_folder(self.local_dir_a))
        row_local_a = QHBoxLayout()
        row_local_a.addWidget(self.local_dir_a)
        row_local_a.addWidget(self.local_btn_a)
        local_layout.addRow("Directorio A (Local):", row_local_a)
        
        self.local_dir_b = QLineEdit()
        self.local_btn_b = QPushButton("Explorar (B)")
        self.local_btn_b.clicked.connect(lambda: self.browse_folder(self.local_dir_b))
        row_local_b = QHBoxLayout()
        row_local_b.addWidget(self.local_dir_b)
        row_local_b.addWidget(self.local_btn_b)
        local_layout.addRow("Directorio B (Local):", row_local_b)
        
        self.local_interval = QSpinBox()
        self.local_interval.setRange(1, 1440)
        self.local_interval.setSuffix(" min")
        local_layout.addRow("Intervalo:", self.local_interval)
        
        self.local_exclusions = QPlainTextEdit()
        self.local_exclusions.setPlaceholderText("Ejemplos:\nName *.log\nPath temp/*\nName .git")
        self.local_exclusions.setToolTip("Un patrón por línea. Use 'Name' para archivos o 'Path' para rutas relativas.")
        local_layout.addRow("Exclusiones:", self.local_exclusions)

        self.local_mode = self.create_mode_combo()
        local_layout.addRow("Modo de sincronización:", self.local_mode)
        
        self.tab_local.setLayout(local_layout)
        self.tabs.addTab(self.tab_local, "Local")

        # --- OneDrive Tab ---
        self.tab_onedrive = QWidget()
        od_layout = QFormLayout()
        od_layout.setVerticalSpacing(8)
        
        self.od_enabled = QCheckBox("Habilitar OneDrive")
        od_layout.addRow(self.od_enabled)

        self.od_local_path = QLineEdit()
        self.od_local_btn = QPushButton("Explorar")
        self.od_local_btn.clicked.connect(lambda: self.browse_folder(self.od_local_path))
        od_row_local = QHBoxLayout()
        od_row_local.addWidget(self.od_local_path)
        od_row_local.addWidget(self.od_local_btn)
        od_layout.addRow("Directorio Local:", od_row_local)
        
        # New: Remote Dir field
        self.od_remote_path = QLineEdit()
        self.od_remote_path.setPlaceholderText("(Opcional) Dejar vacío para raíz")
        od_layout.addRow("Directorio Remoto:", self.od_remote_path)

        self.od_interval = QSpinBox()
        self.od_interval.setRange(1, 1440) # 1 min to 24 hours
        self.od_interval.setSuffix(" min")
        od_layout.addRow("Intervalo:", self.od_interval)

        self.od_exclusions = QPlainTextEdit()
        self.od_exclusions.setPlaceholderText("Ejemplos:\n*.tmp\nnode_modules/\n~*")
        self.od_exclusions.setToolTip("Un patrón por línea. Se aplicará tanto a archivos como a carpetas.")
        od_layout.addRow("Exclusiones:", self.od_exclusions)
        self.od_mode = self.create_mode_combo()
        od_layout.addRow("Modo de sincronización:", self.od_mode)
        
        self.tab_onedrive.setLayout(od_layout)
        self.tabs.addTab(self.tab_onedrive, "OneDrive")

        # --- Google Drive Tab ---
        self.tab_gdrive = QWidget()
        gd_layout = QFormLayout()
        gd_layout.setVerticalSpacing(8)

        self.gd_enabled = QCheckBox("Habilitar Google Drive")
        gd_layout.addRow(self.gd_enabled)

        self.gd_local_path = QLineEdit()
        self.gd_local_btn = QPushButton("Explorar")
        self.gd_local_btn.clicked.connect(lambda: self.browse_folder(self.gd_local_path))
        gd_row_local = QHBoxLayout()
        gd_row_local.addWidget(self.gd_local_path)
        gd_row_local.addWidget(self.gd_local_btn)
        gd_layout.addRow("Directorio Local:", gd_row_local)

        self.gd_remote_path = QLineEdit()
        self.gd_remote_path.setPlaceholderText("NombreRemoto:Ruta (ej. GoogleDrive:/)")
        gd_layout.addRow("Directorio Remoto:", self.gd_remote_path)

        self.gd_interval = QSpinBox()
        self.gd_interval.setRange(1, 1440)
        self.gd_interval.setSuffix(" min")
        gd_layout.addRow("Intervalo:", self.gd_interval)

        self.gd_exclusions = QPlainTextEdit()
        self.gd_exclusions.setPlaceholderText("Ejemplos:\n*.bak\nnode_modules/**\nsecret.key")
        self.gd_exclusions.setToolTip("Un patrón por línea. Formato estándar de rclone.")
        gd_layout.addRow("Exclusiones:", self.gd_exclusions)

        self.gd_mode = self.create_mode_combo()
        gd_layout.addRow("Modo de sincronización:", self.gd_mode)
        
        self.tab_gdrive.setLayout(gd_layout)
        self.tabs.addTab(self.tab_gdrive, "Google Drive")

        # --- Rclone Services Tab ---
        # --- Rclone Services Tab ---
        self.tab_rclone = QWidget()
        rclone_layout = QVBoxLayout()

        self.rclone_table = QTableWidget(0, 3)
        self.rclone_table.setHorizontalHeaderLabels(["Nombre", "Proveedor", "Directorio Local"])
        self.rclone_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.rclone_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.rclone_table.horizontalHeader().setStretchLastSection(True)
        rclone_layout.addWidget(self.rclone_table)

        rclone_btn_row = QHBoxLayout()
        add_btn = QPushButton("Añadir Servicio")
        add_btn.clicked.connect(self.add_rclone_service)
        remove_btn = QPushButton("Eliminar Seleccionado")
        remove_btn.clicked.connect(self.remove_rclone_service)
        rclone_btn_row.addWidget(add_btn)
        rclone_btn_row.addWidget(remove_btn)
        rclone_btn_row.addStretch()
        rclone_layout.addLayout(rclone_btn_row)

        self.tab_rclone.setLayout(rclone_layout)
        self.tabs.addTab(self.tab_rclone, "Servicios Rclone")

        # --- General Tab (Always last) ---
        self.tab_general = QWidget()
        gen_layout = QFormLayout()
        
        self.autostart_checkbox = QCheckBox("Iniciar automáticamente al arrancar el sistema")
        gen_layout.addRow(self.autostart_checkbox)
        
        self.tab_general.setLayout(gen_layout)
        self.tabs.addTab(self.tab_general, "General")
        
        main_layout.addWidget(self.tabs)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.setLayout(main_layout)

    def browse_folder(self, line_edit):
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if folder:
            line_edit.setText(folder)

    def create_mode_combo(self):
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
        desc = combo.itemData(index, Qt.ItemDataRole.ToolTipRole)
        if desc:
            combo.setToolTip(desc)

    def set_mode_combo(self, combo, value):
        idx = combo.findData(value)
        if idx == -1:
            idx = combo.findText("bisync")
        if idx != -1:
            combo.setCurrentIndex(idx)

    def load_settings(self):
        # General
        gen_conf = self.config_manager.get("general", {})
        self.autostart_checkbox.setChecked(gen_conf.get("autostart", False))

        # Local Sync
        loc_conf = self.config_manager.get("local_sync", {})
        self.local_enabled.setChecked(loc_conf.get("enabled", False))
        self.local_dir_a.setText(loc_conf.get("local_dir_a", ""))
        self.local_dir_b.setText(loc_conf.get("local_dir_b", ""))
        self.local_interval.setValue(loc_conf.get("interval_minutes", 15))
        self.local_exclusions.setPlainText(loc_conf.get("exclusions", ""))
        self.set_mode_combo(self.local_mode, loc_conf.get("mode", "bisync"))
        
        # OneDrive
        od_conf = self.config_manager.get("onedrive", {})
        self.od_enabled.setChecked(od_conf.get("enabled", False))
        self.od_local_path.setText(od_conf.get("local_dir", ""))
        self.od_remote_path.setText(od_conf.get("remote_dir", ""))
        self.od_interval.setValue(od_conf.get("interval_minutes", 15))
        self.od_exclusions.setPlainText(od_conf.get("exclusions", ""))
        self.set_mode_combo(self.od_mode, od_conf.get("mode", "bisync"))

        # GDrive
        gd_conf = self.config_manager.get("gdrive", {})
        self.gd_enabled.setChecked(gd_conf.get("enabled", False))
        self.gd_local_path.setText(gd_conf.get("local_dir", ""))
        self.gd_remote_path.setText(gd_conf.get("remote_dir", ""))
        self.gd_interval.setValue(gd_conf.get("interval_minutes", 15))
        self.gd_exclusions.setPlainText(gd_conf.get("exclusions", ""))
        self.set_mode_combo(self.gd_mode, gd_conf.get("mode", "bisync"))

        # Rclone Services
        self.rclone_services = self.config_manager.get("rclone_services", []) or []
        self.refresh_rclone_table()
        self.refresh_rclone_service_tabs()

    def save_settings(self):
        # General
        autostart_enabled = self.autostart_checkbox.isChecked()
        self.config_manager.set("general", {"autostart": autostart_enabled})
        
        from managers.autostart import AutostartManager
        AutostartManager().set_enabled(autostart_enabled)

        self.config_manager.set("local_sync", {
            "enabled": self.local_enabled.isChecked(),
            "local_dir_a": self.local_dir_a.text(),
            "local_dir_b": self.local_dir_b.text(),
            "interval_minutes": self.local_interval.value(),
            "exclusions": self.local_exclusions.toPlainText(),
            "mode": self.local_mode.currentText()
        })

        self.config_manager.set("onedrive", {
            "enabled": self.od_enabled.isChecked(),
            "local_dir": self.od_local_path.text(),
            "remote_dir": self.od_remote_path.text(),
            "interval_minutes": self.od_interval.value(),
            "exclusions": self.od_exclusions.toPlainText(),
            "mode": self.od_mode.currentText()
        })
        
        current_gd = self.config_manager.get("gdrive", {})
        self.config_manager.set("gdrive", {
            "enabled": self.gd_enabled.isChecked(),
            "local_dir": self.gd_local_path.text(),
            "remote_dir": self.gd_remote_path.text(),
            "interval_minutes": self.gd_interval.value(),
            "exclusions": self.gd_exclusions.toPlainText(),
            "mode": self.gd_mode.currentText(),
            "auto_dedupe": current_gd.get("auto_dedupe", True)
        })

        self.apply_rclone_service_tabs()
        self.config_manager.set("rclone_services", self.rclone_services)
        
        self.accept()

    def clear_rclone_service_tabs(self):
        idx = 0
        while idx < self.tabs.count():
            widget = self.tabs.widget(idx)
            if widget and widget.property("rclone_service_tab"):
                self.tabs.removeTab(idx)
                widget.deleteLater()
            else:
                idx += 1

    def refresh_rclone_service_tabs(self):
        self.clear_rclone_service_tabs()
        self.rclone_service_tabs = {}

        insert_at = self.tabs.indexOf(self.tab_rclone)
        for service in self.rclone_services:
            name = service.get("name", "")
            if not name:
                continue

            tab = QWidget()
            tab.setProperty("rclone_service_tab", True)
            layout = QFormLayout()

            enabled = QCheckBox(f"Habilitar {name}")
            enabled.setChecked(service.get("enabled", True))
            layout.addRow(enabled)

            local_path = QLineEdit()
            local_btn = QPushButton("Explorar")
            local_btn.clicked.connect(lambda _, le=local_path: self.browse_folder(le))
            local_row = QHBoxLayout()
            local_row.addWidget(local_path)
            local_row.addWidget(local_btn)
            layout.addRow("Directorio Local:", local_row)
            local_path.setText(service.get("local_dir", ""))

            remote_path = QLineEdit()
            remote_path.setPlaceholderText(f"{name}:/")
            remote_path.setText(service.get("remote_dir", f"{name}:"))
            layout.addRow("Directorio Remoto:", remote_path)

            interval = QSpinBox()
            interval.setRange(1, 1440)
            interval.setSuffix(" min")
            interval.setValue(service.get("interval_minutes", 15))
            layout.addRow("Intervalo:", interval)

            exclusions = QPlainTextEdit()
            exclusions.setPlaceholderText("Ejemplos:\n*.tmp\nnode_modules/\n~*")
            exclusions.setToolTip("Un patrón por línea. Formato estándar de rclone.")
            exclusions.setPlainText(service.get("exclusions", ""))
            layout.addRow("Exclusiones:", exclusions)

            mode_combo = self.create_mode_combo()
            self.set_mode_combo(mode_combo, service.get("mode", "bisync"))
            layout.addRow("Modo de sincronización:", mode_combo)

            tab.setLayout(layout)
            self.tabs.insertTab(insert_at, tab, name)
            insert_at += 1

            self.rclone_service_tabs[name] = {
                "enabled": enabled,
                "local_dir": local_path,
                "remote_dir": remote_path,
                "interval": interval,
                "exclusions": exclusions,
                "mode": mode_combo
            }

    def apply_rclone_service_tabs(self):
        for service in self.rclone_services:
            name = service.get("name", "")
            widgets = self.rclone_service_tabs.get(name)
            if not widgets:
                continue
            service["enabled"] = widgets["enabled"].isChecked()
            service["local_dir"] = widgets["local_dir"].text()
            service["remote_dir"] = widgets["remote_dir"].text()
            service["interval_minutes"] = widgets["interval"].value()
            service["exclusions"] = widgets["exclusions"].toPlainText()
            service["mode"] = widgets["mode"].currentText()

    def refresh_rclone_table(self):
        self.rclone_table.setRowCount(0)
        for service in self.rclone_services:
            row = self.rclone_table.rowCount()
            self.rclone_table.insertRow(row)
            self.rclone_table.setItem(row, 0, QTableWidgetItem(service.get("name", "")))
            self.rclone_table.setItem(row, 1, QTableWidgetItem(service.get("provider", "")))
            self.rclone_table.setItem(row, 2, QTableWidgetItem(service.get("local_dir", "")))

    def add_rclone_service(self):
        dialog = RcloneServiceDialog(self)
        if dialog.exec():
            service = dialog.get_service()
            if any(s.get("name", "").lower() == service.get("name", "").lower() for s in self.rclone_services):
                QMessageBox.warning(self, "Duplicado", "Ya existe un servicio con ese nombre.")
                return
            service.setdefault("remote_dir", f"{service.get('name', '').strip()}:")
            service.setdefault("interval_minutes", 15)
            service.setdefault("enabled", True)
            service.setdefault("exclusions", "")
            service.setdefault("mode", "bisync")
            service.setdefault("mode", "bisync")
            self.rclone_services.append(service)
            self.refresh_rclone_table()
            self.refresh_rclone_service_tabs()
            self.select_rclone_service_tab(service.get("name", ""))

    def remove_rclone_service(self):
        selected = self.rclone_table.selectionModel().selectedRows()
        if not selected:
            return
        for index in sorted([s.row() for s in selected], reverse=True):
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
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if answer != QMessageBox.StandardButton.Yes:
                continue

            terminal = RcloneConfigTerminalDialog(
                "Eliminar Servicio Rclone",
                f"Terminal interactiva para eliminar '{name}'. Sigue el flujo de rclone config (opción 'd').",
                self
            )
            terminal.exec()

            del self.rclone_services[index]
        self.refresh_rclone_table()
        self.refresh_rclone_service_tabs()

    def select_rclone_service_tab(self, name):
        for idx in range(self.tabs.count()):
            if self.tabs.tabText(idx) == name:
                self.tabs.setCurrentIndex(idx)
                return
