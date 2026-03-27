# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QProcess
from managers.rclone_service import ProcessWorker
import subprocess
import os
import re
from datetime import datetime

class LocalSyncManager(QObject):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    sync_finished = pyqtSignal(int)
    progress_updated = pyqtSignal(str, dict)  # (service_key, data) — conectado desde main_window
    
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
        self.worker = None  # ProcessWorker (QThread)
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
        if self.is_running and self.worker:
            self.worker.stop()
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

        mode = self._get_mode()
        cmd = self._build_rclone_command(mode, dir_a, dir_b)
        
        # Apply Exclusions
        exclusions_str = self.config_manager.get("local_sync", {}).get("exclusions", "")
        if exclusions_str:
            for pattern in exclusions_str.splitlines():
                if pattern.strip():
                    cmd.extend(["--exclude", pattern.strip()])

        if mode == "bisync":
            if force_resync or self.force_resync_next:
                if "--resync" not in cmd:
                    cmd.append("--resync")
                self.force_resync_next = False
                self.log_message.emit("Local: Re-sincronización forzada activada.")
        else:
            if force_resync or self.force_resync_next:
                self.force_resync_next = False
                self.log_message.emit("Local: El modo actual no admite --resync; se reinicia la sincronización.")

        self.start_process(cmd)

    def force_resync(self):
        if self.is_running:
            self.force_resync_next = True
            self.log_message.emit("Local: Re-sincronización programada al finalizar.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def _get_mode(self):
        return self.config_manager.get("local_sync", {}).get("mode", "bisync")

    def _build_rclone_command(self, mode, src, dst):
        action = "bisync"
        extras = ["--create-empty-src-dirs"]
        if mode == "copy":
            action = "copy"
        elif mode == "sync":
            action = "sync"
            extras = []

        cmd = [
            "rclone", action, src, dst, "--verbose", "--checksum", "--progress",
            "--stats", "1s", "--stats-one-line", "--local-no-check-updated"
        ]
        if extras:
            cmd.extend(extras)
        return cmd

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
        # Dividir por salto de línea Y por retorno de carro para capturar líneas de progreso de rclone
        for line in re.split(r'[\r\n]+', data):
            clean_line = self.clean_log(line)
            if clean_line:
                self.log_message.emit(f"[Local] {clean_line}")
                self.check_resync_trigger(clean_line)
                self._emit_progress(clean_line)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        # Dividir por salto de línea Y por retorno de carro
        for line in re.split(r'[\r\n]+', data):
            clean_line = self.clean_log(line)
            if not clean_line: continue
            
            # Rclone sends INFO to stderr. Only tag as Error if it really is one.
            if "ERROR" in clean_line or "Failed" in clean_line:
                self.log_message.emit(f"[Local Error] {clean_line}")
            else:
                self.log_message.emit(f"[Local] {clean_line}")
            
            self.check_resync_trigger(clean_line)
            self._emit_progress(clean_line)

    def _emit_progress(self, line):
        # Parsear la línea de estadísticas de rclone y emitir hacia la UI
        match = re.search(r'(\d+)%', line)
        if not match:
            return
        data = {"percent": int(match.group(1))}
        speed_match = re.search(r'([\d\.]+ [KMGT]?i?[Bb]/s)', line)
        if speed_match:
            data["speed"] = speed_match.group(1)
        eta_match = re.search(r'ETA (.*)', line)
        if eta_match:
            data["eta"] = eta_match.group(1).strip()
        data["event"] = "error" if re.search(r"error|failed|panic", line, re.IGNORECASE) else "progress"
        self.progress_updated.emit("local_sync", data)

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
        # Reutiliza ProcessWorker (igual que Mega-Dev) para heredar su canal update_ui comprobado
        self.is_running = True
        self.needs_resync = False
        self.last_cmd_args = cmd_list
        self.status_changed.emit("Sincronizando")
        self.log_message.emit("Local: Iniciando sincronización...")
        
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        
        self.worker = ProcessWorker("Local", "local_sync", cmd_list)
        self.worker.log_line.connect(self._on_worker_line)
        self.worker.update_ui.connect(self._on_worker_update)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_worker_line(self, _svc, line):
        clean = self.clean_log(line)
        if not clean:
            return
        if "ERROR" in clean or "Failed" in clean:
            self.log_message.emit(f"[Local Error] {clean}")
        else:
            self.log_message.emit(f"[Local] {clean}")
        self.check_resync_trigger(clean)

    def _on_worker_update(self, service_key, percent, event_type):
        # Reenvía el evento del worker como progress_updated (igual a RcloneServiceManager)
        payload = {"percent": percent, "event": event_type}
        self.progress_updated.emit(service_key, payload)

    def _on_worker_finished(self, exit_code):
        return self.process_finished(exit_code, None)

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
