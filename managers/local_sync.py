
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QProcess
import subprocess
import os
import re
from datetime import datetime

class LocalSyncManager(QObject):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    sync_finished = pyqtSignal(int)
    
    def __init__(self, config_manager, coordinator):
        super().__init__()
        self.config_manager = config_manager
        self.coordinator = coordinator
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.coordinator.lock_released.connect(self.on_lock_released)
        self.is_running = False
        self.is_waiting = False
        self.process = None
        self.active_dirs = []
        self.force_resync_next = False

    def start_timer(self):
        enabled = self.config_manager.get("local_sync", {}).get("enabled", False)
        if enabled:
            interval_minutes = self.config_manager.get("local_sync", {}).get("interval_minutes", 15)
            self.timer.start(interval_minutes * 60 * 1000)
            if not self.is_running:
                self.status_changed.emit("Activo")
        else:
            self.timer.stop()
            self.status_changed.emit("Desactivado")

    def stop_timer(self):
        self.timer.stop()
        if self.is_running and self.process:
            self.process.terminate()
        self.status_changed.emit("Detenido")

    def on_lock_released(self, released_path):
        """ Reintenta si estábamos esperando por esta ruta. """
        dir_a = self.config_manager.get("local_sync", {}).get("local_dir_a")
        dir_b = self.config_manager.get("local_sync", {}).get("local_dir_b")
        
        # Si alguna de nuestras carpetas fue liberada y estamos en espera...
        is_relevant = (released_path == os.path.abspath(dir_a or "") or released_path == os.path.abspath(dir_b or ""))
        if is_relevant and self.is_waiting and not self.is_running:
             QTimer.singleShot(1000, self.sync)

    def sync(self, force_resync=False):
        if self.is_running:
            return

        dir_a = self.config_manager.get("local_sync", {}).get("local_dir_a")
        dir_b = self.config_manager.get("local_sync", {}).get("local_dir_b")

        if not dir_a or not os.path.exists(dir_a):
            self.log_message.emit("Local: Error - Directorio A no válido")
            self.status_changed.emit("Error Config")
            return
        
        if not dir_b or not os.path.exists(dir_b):
             self.log_message.emit("Local: Error - Directorio B no válido")
             self.status_changed.emit("Error Config")
             return

        # Check Path Coordination for BOTH dirs
        busy_a = self.coordinator.is_path_busy(dir_a)
        busy_b = self.coordinator.is_path_busy(dir_b)
        
        if busy_a or busy_b:
            self.is_waiting = True
            self.status_changed.emit("En Espera")
            busy_p = dir_a if busy_a else dir_b
            self.log_message.emit(f"Local: Esperando porque la ruta {busy_p} está ocupada.")
            return
        
        self.is_waiting = False

        # Clean up stale rclone bisync lock files (.ick/.lck)
        self.cleanup_rclone_lock_files()

        # Acquire locks for both
        self.coordinator.acquire_lock(dir_a, "LocalSync")
        self.coordinator.acquire_lock(dir_b, "LocalSync")
        self.active_dirs = [dir_a, dir_b]

        cmd = ["rclone", "bisync", dir_a, dir_b, "--verbose", "--create-empty-src-dirs", "--checksum"]
        
        # Apply Exclusions
        exclusions_str = self.config_manager.get("local_sync", {}).get("exclusions", "")
        if exclusions_str:
            for pattern in exclusions_str.splitlines():
                if pattern.strip():
                    cmd.extend(["--exclude", pattern.strip()])

        if force_resync or self.force_resync_next:
            if "--resync" not in cmd:
                cmd.append("--resync")
            self.force_resync_next = False
            self.log_message.emit("Local: Re-sincronización forzada activada.")

        self.start_process(cmd)

    def force_resync(self):
        if self.is_running:
            self.force_resync_next = True
            self.log_message.emit("Local: Re-sincronización programada al finalizar.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def cleanup_rclone_lock_files(self):
        cache_dir = os.path.expanduser("~/.cache/rclone/bisync")
        if not os.path.isdir(cache_dir):
            return
        removed = 0
        for root, _, files in os.walk(cache_dir):
            for filename in files:
                if filename.endswith(".ick") or filename.endswith(".lck"):
                    try:
                        os.remove(os.path.join(root, filename))
                        removed += 1
                    except OSError:
                        continue
        if removed:
            self.log_message.emit(f"Local: Eliminados {removed} archivos de bloqueo de Rclone (.ick/.lck).")

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        for line in data.splitlines():
             clean_line = self.clean_log(line)
             if clean_line:
                self.log_message.emit(f"[Local] {clean_line}")
                self.check_resync_trigger(clean_line)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        for line in data.splitlines():
            clean_line = self.clean_log(line)
            if not clean_line: continue
            
            # Rclone sends INFO to stderr. Only tag as Error if it really is one.
            if "ERROR" in clean_line or "Failed" in clean_line:
                self.log_message.emit(f"[Local Error] {clean_line}")
            else:
                self.log_message.emit(f"[Local] {clean_line}")
            
            self.check_resync_trigger(clean_line)

    def clean_log(self, text):
        # Strip ANSI codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text).strip()
        
        # Filter out some very verbose spam if desired, or keep it clean
        if not text: return None
        return text

    def check_resync_trigger(self, line):
        # Rclone bisync specific error for resync
        # "Safety abort" happens when too many files are deleted/changed. 
        # Usually implies the sync history is invalid (e.g. user changed dirs).
        # We generally want to RESYNC (re-establish baseline) rather than FORCE (execute deletes).
        triggers = ["Must run --resync", "use --resync", "Safety abort"]
        if any(t in line for t in triggers):
            self.log_message.emit("Local: Detectado error de seguridad/historial. Se requiere Re-sincronización.")
            self.needs_resync = True

    def start_process(self, cmd_list):
        self.is_running = True
        self.needs_resync = False # Reset flag
        self.status_changed.emit("Sincronizando...")
        self.log_message.emit("Local: Iniciando sincronización...")
        
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        
        # Use functools.partial or lambda to pass cmd_list if needed, 
        # but storing it in 'last_cmd' member might be easier for checking in finished
        self.last_cmd_args = cmd_list
        self.process.finished.connect(self.process_finished)
        
        self.process.start(cmd_list[0], cmd_list[1:])

    def process_finished(self, exit_code, exit_status):
        self.is_running = False
        timestamp = int(datetime.now().timestamp())
        
        # Release path locks
        for d in self.active_dirs:
            self.coordinator.release_lock(d)
        self.active_dirs = []

        if self.needs_resync:
            self.log_message.emit("Local: Ejecutando --resync de recuperación...")
            new_cmd = self.last_cmd_args + ["--resync"]
            # Avoid infinite loops by not setting needs_resync in the next run implicitly? 
            # Or assume if resync fails, it's a hard error.
            self.start_process(new_cmd)
            return

        if self.force_resync_next:
            self.force_resync_next = False
            self.log_message.emit("Local: Ejecutando re-sincronización programada...")
            self.sync(force_resync=True)
            return

        if exit_code == 0:
            self.status_changed.emit("Activo")
            self.sync_finished.emit(timestamp)
            self.log_message.emit("Local: Sincronización completada.")
        else:
            self.status_changed.emit("Error")
            self.log_message.emit(f"Local: Finalizado con Error (Código {exit_code}).")
            self.log_message.emit("Local: Revise el log para detalles específicos de 'rclone bisync'.")
        
        self.process = None
