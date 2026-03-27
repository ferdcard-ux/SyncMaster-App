# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QProcess
import os
import shutil
from datetime import datetime
import socket

class OneDriveManager(QObject):
    status_changed = pyqtSignal(str) # High level status: Active, Syncing, etc.
    log_message = pyqtSignal(str)    # Detailed log for the black screen
    sync_finished = pyqtSignal(int)  # To notify main window of completion (unix timestamp)

    def __init__(self, config_manager, coordinator):
        super().__init__()
        self.config_manager = config_manager
        self.coordinator = coordinator
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.coordinator.lock_released.connect(self.on_lock_released)
        
        self.process = None 
        self.is_running = False
        self.is_waiting = False
        self.current_cmd = []
        self.needs_resync = False
        self.force_resync_next = False
        self.activity_timer = QTimer()
        self.activity_timer.setSingleShot(True)
        self.activity_timer.timeout.connect(self._mark_idle_state)

    def start_timer(self):
        enabled = self.config_manager.get("onedrive", {}).get("enabled", False)
        if enabled:
            interval_minutes = self.config_manager.get("onedrive", {}).get("interval_minutes", 15)
            self.timer.start(interval_minutes * 60 * 1000)
            self.status_changed.emit("Activo")
        else:
            self.timer.stop()
            self.status_changed.emit("Desactivado")

    def stop_timer(self):
        self.timer.stop()
        if self.is_running and self.process:
            self.process.terminate()
        self.status_changed.emit("Detenido")

    def configure_onedrive(self, local_path, remote_folder, force_resync=False):
        """ Configura OneDrive de forma aislada. """
        base_config_dir = os.path.expanduser("~/.config/syncmaster/onedrive/")
        config_file = os.path.join(base_config_dir, "config")
        sync_list_file = os.path.join(base_config_dir, "sync_list")

        if not local_path or not os.path.exists(local_path):
             raise ValueError(f"El directorio local no existe: {local_path}")

        # Stop previous service and lingering processes
        stop_proc = QProcess()
        stop_proc.start("systemctl", ["--user", "stop", "onedrive.service"])
        stop_proc.waitForFinished(1000) # Wait at most 1s
        
        kill_proc = QProcess()
        kill_proc.start("pkill", ["-f", "onedrive --sync"])
        kill_proc.waitForFinished(1000)

        os.makedirs(base_config_dir, exist_ok=True)

        # Estrategia de Mapeo
        # El cliente 'onedrive' hace espejo. Para sincronizar Local/X <-> Remote/X,
        # debemos configurar sync_dir = Local (parent) y sync_list = /X.
        
        final_sync_dir = local_path
        use_sync_list = False
        target_remote = ""

        if remote_folder:
            clean_remote = remote_folder.strip().strip("/")
            local_name = os.path.basename(os.path.normpath(local_path))
            
            # Si el usuario especifica una carpeta remota (ej. Documentos)
            # Intentamos usar la Estrategia del Padre si coinciden los nombres
            if clean_remote.lower() == local_name.lower():
                final_sync_dir = os.path.dirname(os.path.normpath(local_path))
                target_remote = f"/{clean_remote}"
                use_sync_list = True
                print(f"DEBUG: Estrategia Padre activada. SyncDir: {final_sync_dir}, Target: {target_remote}")
            else:
                # Si no coinciden (ej. Local/MisDocs <-> Remote/Documentos),
                # 'onedrive' no soporta esto nativamente sin enlaces simbólicos o trucos.
                # Fallback: SyncDir = LocalPath (Sincroniza a la RAÍZ remota)
                print(f"DEBUG: Nombres no coinciden ({local_name} != {clean_remote}). Sincronizando a RAÍZ remota.")
                if os.path.exists(sync_list_file): os.remove(sync_list_file)
        else:
            # Sin carpeta remota -> Sincroniza LocalPath <-> Raíz Remota
            if os.path.exists(sync_list_file): os.remove(sync_list_file)

        # 5. Escribir archivo 'config'
        os.makedirs(os.path.join(base_config_dir, "logs"), exist_ok=True)
        with open(config_file, "w") as f:
            f.write(f'sync_dir = "{final_sync_dir}"\n')
            f.write('skip_dir = ""\n')
            f.write(f'log_dir = "{os.path.join(base_config_dir, "logs")}/"\n')
            # Throttling and Timeouts for stability (Must be quoted)
            f.write('threads = "2"\n')
            f.write('connect_timeout = "60"\n')
            f.write('data_timeout = "300"\n')
            
            # Apply Exclusions (Merging defaults with user patterns)
            default_skips = ["~*", ".~*", "*.tmp", "*.swp", "*.partial"]
            exclusions_str = self.config_manager.get("onedrive", {}).get("exclusions", "")
            user_patterns = [p.strip() for p in exclusions_str.splitlines() if p.strip()]
            
            final_patterns = list(dict.fromkeys(default_skips + user_patterns))
            joined = "|".join(final_patterns)
            f.write(f'skip_file = "{joined}"\n')
            f.write(f'skip_dir = "{joined}"\n')
        
        # 6. Escribir sync_list si aplica
        if use_sync_list and target_remote:
             with open(sync_list_file, "w") as f:
                    f.write(f"{target_remote}\n")
                    
        cmd = [
            "onedrive",
            "--sync",
            "--confdir",
            base_config_dir,
            "--verbose",
            "--disable-notifications",
            "--force-http-11"
        ]

        if force_resync:
            cmd.append("--resync")
        else:
            cmd.insert(-1, "--force")

        return cmd

    def on_lock_released(self, released_path):
        local_dir = self.config_manager.get("onedrive", {}).get("local_dir")
        if local_dir and released_path == os.path.abspath(local_dir) and self.is_waiting and not self.is_running:
            # Use singleShot to break signal chain and avoid recursion
            QTimer.singleShot(1000, self.sync)

    def check_connectivity(self):
        """ Checks if Microsoft Graph is reachable. """
        try:
            socket.create_connection(("graph.microsoft.com", 443), timeout=5)
            return True
        except (socket.timeout, socket.error):
            return False

    def sync(self, force_resync=False):
        if self.is_running:
            return

        # Connectivity Guard
        if not self.check_connectivity():
            self.status_changed.emit("Sin Conexión")
            self.log_message.emit("OneDrive: Sin conexión con Microsoft. Reintentando luego...")
            return

        self.local_dir = self.config_manager.get("onedrive", {}).get("local_dir")
        remote_dir = self.config_manager.get("onedrive", {}).get("remote_dir")

        if not self.local_dir or not os.path.exists(self.local_dir):
             self.log_message.emit("OneDrive: NO CONFIGURADO o ruta no existe.")
             self.status_changed.emit("Error Config")
             return

        # Check Path Coordination
        if not self.coordinator.acquire_lock(self.local_dir, "OneDrive"):
            self.is_waiting = True
            self.status_changed.emit("En Espera")
            self.log_message.emit(f"OneDrive: Esperando porque la ruta {self.local_dir} está ocupada.")
            return
        
        self.is_waiting = False

        # Check Auth
        default_token = os.path.expanduser("~/.config/onedrive/refresh_token")
        target_token = os.path.expanduser("~/.config/syncmaster/onedrive/refresh_token")
        
        if os.path.exists(default_token) and not os.path.exists(target_token):
            os.makedirs(os.path.dirname(target_token), exist_ok=True)
            shutil.copy2(default_token, target_token)

        if not os.path.exists(target_token):
             self.log_message.emit("OneDrive: NO AUTENTICADO. Ejecute 'onedrive' en terminal.")
             self.status_changed.emit("Error Auth")
             self.coordinator.release_lock(self.local_dir)
             return

        should_resync = force_resync or self.force_resync_next
        if should_resync:
            self.force_resync_next = False
            self.log_message.emit("OneDrive: Re-sincronización forzada activada.")

        try:
            self.current_cmd = self.configure_onedrive(self.local_dir, remote_dir, force_resync=should_resync)
        except Exception as e:
            self.log_message.emit(f"OneDrive Config Error: {str(e)}")
            self.coordinator.release_lock(self.local_dir)
            return

        self.start_process(self.current_cmd)

    def force_resync(self):
        if self.is_running:
            self.force_resync_next = True
            self.log_message.emit("OneDrive: Re-sincronización programada al finalizar.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def start_process(self, cmd_list):
        self.is_running = True
        self.current_cmd = cmd_list
        self.needs_resync = False # Reset flag for this run
        self.status_changed.emit("Sincronizando")
        
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

        program = cmd_list[0]
        args = cmd_list[1:]
        self.process.start(program, args)
        self.log_message.emit(f"OneDrive: Ejecutando: {' '.join(cmd_list)}")
        self.activity_timer.start(8000)

    def handle_stdout(self):
        data_bytes = self.process.readAllStandardOutput().data()
        data = data_bytes.decode(errors="ignore")
        
        # 1. Raw Prompt Detection (even without newline)
        # Handle variations: [y/N], [Y/n], [y/n], [Y/N], (y/n), etc.
        data_lower = data.lower()
        if "?" in data and ("y/n" in data_lower):
             self.log_message.emit(f"[OD Prompt] Respondiendo 'y' a: {data.strip()}")
             self.process.write(b"y\n")
             self.process.waitForBytesWritten() # Ensure it's sent to stdin immediately

        # 2. Line based logging
        is_resync = "--resync" in " ".join(self.current_cmd)
        
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue

            # During resync, we want to see EVERYTHING
            if is_resync or any(k in line for k in ["Uploading", "Downloading", "Deleting", "Error", "Syncing"]):
                self.log_message.emit(f"[OD] {line}")
                self._mark_sync_activity()

            # Detect Resync Requirement (Standard Run)
            if "resync is required" in line.lower() or "run --resync" in line.lower():
                self.log_message.emit("[OD] Se requiere --resync. Se reiniciará automáticamente...")
                self.needs_resync = True

    def handle_stderr(self):
        data_bytes = self.process.readAllStandardError().data()
        data = data_bytes.decode(errors="ignore")

        # 1. Raw Prompt Detection (even without newline)
        data_lower = data.lower()
        if "?" in data and ("y/n" in data_lower):
            self.log_message.emit(f"[OD Prompt stderr] Respondiendo 'y' a: {data.strip()}")
            self.process.write(b"y\n")
            self.process.waitForBytesWritten()

        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue

            # Filter out known cURL/HTTP2 bugs warning to avoid user confusion
            if "curl" in line.lower() and "http/2" in line.lower():
                continue

            # Log info/error (Always log stderr for visibility during debugging/resync)
            self.log_message.emit(f"[OD Info/Err] {line}")
            self._mark_sync_activity()

    def process_finished(self, exit_code, exit_status):
        self.is_running = False
        timestamp = int(datetime.now().timestamp())
        self.activity_timer.stop()
        
        # Release path lock
        if self.local_dir:
            self.coordinator.release_lock(self.local_dir)

        # Auto-Restart for Resync
        if self.needs_resync:
            # Defensive check: if current command HAS --resync, don't trigger another one automatically
            if "--resync" in self.current_cmd:
                self.log_message.emit("OneDrive: Falló la recuperación (--resync). Se reintentará en el próximo intervalo.")
                self.needs_resync = False
            else:
                self.log_message.emit("OneDrive: Iniciando modo de Recuperación (--resync)...")
                # Append --resync if not present
                cmd_copy = list(self.current_cmd)
                if "--resync" not in cmd_copy:
                    cmd_copy.append("--resync")
                    # CRITICAL: --force and --resync are incompatible
                    if "--force" in cmd_copy:
                        cmd_copy.remove("--force")
                
                # Restart process with the new command
                self.start_process(cmd_copy)
                return

        if exit_code == 0:
            self.status_changed.emit("Activo")
            self.sync_finished.emit(timestamp)
            self.log_message.emit("OneDrive: Sincronización completada.")
        else:
            self.status_changed.emit("Error")
            self.log_message.emit(f"OneDrive: Finalizado con error (Código {exit_code})")
            # If it failed with code 126 (which sometimes happens if the binary is bad or blocked), 
            # we should log it clearly. 
        
        self.process = None

    def _mark_sync_activity(self):
        if not self.is_running:
            return
        self.status_changed.emit("Sincronizando")
        self.activity_timer.start(8000)

    def _mark_idle_state(self):
        if not self.is_running:
            return
        self.status_changed.emit("Activo")
