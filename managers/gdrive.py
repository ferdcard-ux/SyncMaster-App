
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QProcess
import subprocess
import os
import re
from datetime import datetime
import socket

class GDriveManager(QObject):
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
        self.process = None
        self.is_running = False
        self.is_waiting = False
        self.local_dir = None
        self.remote_dir = None
        self.force_resync_next = False
        self.dedupe_process = None
        self.is_deduping = False

    def start_timer(self):
        enabled = self.config_manager.get("gdrive", {}).get("enabled", False)
        if enabled:
            interval_minutes = self.config_manager.get("gdrive", {}).get("interval_minutes", 15)
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
        local_dir = self.config_manager.get("gdrive", {}).get("local_dir")
        if local_dir and released_path == os.path.abspath(local_dir) and self.is_waiting and not self.is_running:
            QTimer.singleShot(1000, self.sync)

    def check_connectivity(self):
        """ Checks if Google API is reachable. """
        try:
            # Check www.googleapis.com on port 443
            socket.create_connection(("www.googleapis.com", 443), timeout=5)
            return True
        except (socket.timeout, socket.error):
            return False

    def sync(self, force_resync=False):
        if self.is_running or self.is_deduping:
            return
        
        # Connectivity Guard
        if not self.check_connectivity():
            self.status_changed.emit("Sin Conexión")
            self.log_message.emit("GDrive: Sin conexión con Google Servers. Reintentando luego...")
            return

        self.local_dir = self.config_manager.get("gdrive", {}).get("local_dir")
        self.remote_dir = self.config_manager.get("gdrive", {}).get("remote_dir")

        if not self.local_dir or not os.path.exists(self.local_dir):
            self.log_message.emit("GDrive: Error - Directorio local no válido")
            self.status_changed.emit("Error Config")
            return
        
        if not self.remote_dir:
             self.log_message.emit("GDrive: Error - Directorio remoto no configurado")
             self.status_changed.emit("Error Config")
             return

        # Check Path Coordination
        if not self.coordinator.acquire_lock(self.local_dir, "GDrive"):
            self.is_waiting = True
            self.status_changed.emit("En Espera")
            self.log_message.emit(f"GDrive: Esperando porque la ruta {self.local_dir} está ocupada.")
            return
        
        self.is_waiting = False

        cmd = ["rclone", "bisync", self.local_dir, self.remote_dir, "--verbose", "--checksum"]
        exclusions_str = self.config_manager.get("gdrive", {}).get("exclusions", "")
        if exclusions_str:
            for pattern in exclusions_str.splitlines():
                if pattern.strip():
                    cmd.extend(["--exclude", pattern.strip()])
                    
        if force_resync or self.force_resync_next:
            if "--resync" not in cmd:
                cmd.append("--resync")
            self.force_resync_next = False
            self.log_message.emit("GDrive: Re-sincronización forzada activada.")

        self.start_process(cmd)

    def force_resync(self):
        if self.is_running or self.is_deduping:
            self.force_resync_next = True
            self.log_message.emit("GDrive: Re-sincronización programada al finalizar.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def start_process(self, cmd_list):
        self.is_running = True
        self.current_cmd = cmd_list
        self.needs_resync = False
        self.status_changed.emit("Sincronizando...")
        self.log_message.emit(f"GDrive: Iniciando sincronización...")
        
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        
        self.process.start(cmd_list[0], cmd_list[1:])

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        for line in data.splitlines():
             clean_line = self.clean_log(line)
             if clean_line:
                self.log_message.emit(f"[GDrive] {clean_line}")
                self.check_resync_trigger(clean_line)
                self.check_prompt(clean_line)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        for line in data.splitlines():
            clean_line = self.clean_log(line)
            if not clean_line: continue

            if "ERROR" in clean_line or "Failed" in clean_line:
                # Distinguish network errors in logs
                network_errors = ["network is unreachable", "connection refused", "timeout", "SSL connect error"]
                if any(e.lower() in clean_line.lower() for e in network_errors):
                    self.log_message.emit(f"[GDrive Red] {clean_line}")
                    self.status_changed.emit("Sin Conexión")
                else:
                    self.log_message.emit(f"[GDrive Error] {clean_line}")
            else:
                self.log_message.emit(f"[GDrive] {clean_line}")
            
            self.check_resync_trigger(clean_line)
            self.check_prompt(clean_line)

    def check_resync_trigger(self, line):
        # Prevent resync loops on network errors
        network_errors = ["network is unreachable", "connection refused", "timeout", "SSL connect error", "failed to create file system"]
        if any(e.lower() in line.lower() for e in network_errors):
            # If we hit a network error, we definitely DON'T want to trigger a resync
            self.needs_resync = False 
            return

        triggers = ["Must run --resync", "bisync aborted", "run --resync", "critical error"]
        if any(t.lower() in line.lower() for t in triggers):
            if not self.needs_resync:
                self.log_message.emit("GDrive: Detectado error crítico de historial. Se requiere Re-sincronización (--resync).")
            self.needs_resync = True

    def check_prompt(self, line):
        if "?" in line and "[y/N]" in line:
             self.log_message.emit(f"[GDrive] Confirmando prompt: {line}")
             self.process.write(b"y\n")

    def clean_log(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text).strip()

    def process_finished(self, exit_code, exit_status):
        self.is_running = False
        timestamp = int(datetime.now().timestamp())
        
        # Release path lock
        if self.local_dir:
            self.coordinator.release_lock(self.local_dir)

        if self.needs_resync:
            # Defensive check: if current command HAS --resync, don't trigger another one automatically
            if "--resync" in self.current_cmd:
                self.log_message.emit("GDrive: Falló la actualización crítica (--resync). Se reintentará en el próximo intervalo.")
                self.needs_resync = False
            else:
                # Only attempt auto-resync if we HAVE connection
                if self.check_connectivity():
                    self.log_message.emit("GDrive: Ejecutando auto-recuperación (--resync)...")
                    cmd_copy = list(self.current_cmd)
                    if "--resync" not in cmd_copy:
                        cmd_copy.append("--resync")
                    self.start_process(cmd_copy)
                    return
                else:
                    self.log_message.emit("GDrive: Error crítico de historial, pero no hay conexión para recuperar. Esperando...")
                    self.needs_resync = True # Keep flag for next successful sync attempt
        if self.force_resync_next:
            self.force_resync_next = False
            self.log_message.emit("GDrive: Ejecutando re-sincronización programada...")
            self.sync(force_resync=True)
            return

        if exit_code == 0:
            self.status_changed.emit("Activo")
            self.sync_finished.emit(timestamp)
            self.log_message.emit("GDrive: Sincronización completada.")
            if self.config_manager.get("gdrive", {}).get("auto_dedupe", True):
                self.start_dedupe()
        else:
            self.status_changed.emit("Error")
            self.log_message.emit(f"GDrive: Error (Código {exit_code}). Verifique logs.")
        
        self.process = None

    def start_dedupe(self):
        if self.is_deduping or not self.remote_dir:
            return

        self.is_deduping = True
        self.log_message.emit("GDrive: Iniciando deduplicación automática (rclone dedupe)...")

        cmd = ["rclone", "dedupe", "--dedupe-mode", "newest", "--verbose", self.remote_dir]

        self.dedupe_process = QProcess()
        self.dedupe_process.readyReadStandardOutput.connect(self.handle_dedupe_stdout)
        self.dedupe_process.readyReadStandardError.connect(self.handle_dedupe_stderr)
        self.dedupe_process.finished.connect(self.dedupe_finished)
        self.dedupe_process.start(cmd[0], cmd[1:])

    def handle_dedupe_stdout(self):
        data = self.dedupe_process.readAllStandardOutput().data().decode()
        for line in data.splitlines():
            clean_line = self.clean_log(line)
            if clean_line:
                self.log_message.emit(f"[GDrive Dedupe] {clean_line}")

    def handle_dedupe_stderr(self):
        data = self.dedupe_process.readAllStandardError().data().decode()
        for line in data.splitlines():
            clean_line = self.clean_log(line)
            if clean_line:
                self.log_message.emit(f"[GDrive Dedupe] {clean_line}")

    def dedupe_finished(self, exit_code, exit_status):
        self.is_deduping = False
        if exit_code == 0:
            self.log_message.emit("GDrive: Deduplicación finalizada correctamente.")
        else:
            self.log_message.emit(f"GDrive: Deduplicación finalizó con error (Código {exit_code}).")
        self.dedupe_process = None
