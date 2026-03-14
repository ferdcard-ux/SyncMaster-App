from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QProcess
import os
import re
from datetime import datetime


class RcloneServiceManager(QObject):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    sync_finished = pyqtSignal(int)

    def __init__(self, config_manager, coordinator, service_name):
        super().__init__()
        self.config_manager = config_manager
        self.coordinator = coordinator
        self.service_name = service_name
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.coordinator.lock_released.connect(self.on_lock_released)
        self.process = None
        self.is_running = False
        self.is_waiting = False
        self.local_dir = None
        self.remote_dir = None
        self.needs_resync = False
        self.force_resync_next = False
        self.current_cmd = []

    def _get_service_config(self):
        services = self.config_manager.get("rclone_services", []) or []
        for service in services:
            if service.get("name") == self.service_name:
                return service
        return None

    def start_timer(self):
        conf = self._get_service_config()
        if not conf:
            self.timer.stop()
            self.status_changed.emit("Desactivado")
            return

        enabled = conf.get("enabled", True)
        if enabled:
            interval_minutes = conf.get("interval_minutes", 15)
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
        conf = self._get_service_config()
        if not conf:
            return
        local_dir = conf.get("local_dir")
        if local_dir and released_path == os.path.abspath(local_dir) and self.is_waiting and not self.is_running:
            QTimer.singleShot(1000, self.sync)

    def sync(self, force_resync=False):
        if self.is_running:
            return

        conf = self._get_service_config()
        if not conf:
            self.status_changed.emit("Desactivado")
            return

        self.local_dir = conf.get("local_dir")
        self.remote_dir = conf.get("remote_dir") or f"{self.service_name}:"

        if not self.local_dir or not os.path.exists(self.local_dir):
            self.log_message.emit(f"{self.service_name}: Error - Directorio local no válido")
            self.status_changed.emit("Error Config")
            return

        if not self.remote_dir:
            self.log_message.emit(f"{self.service_name}: Error - Directorio remoto no configurado")
            self.status_changed.emit("Error Config")
            return

        if not self.coordinator.acquire_lock(self.local_dir, f"Rclone:{self.service_name}"):
            self.is_waiting = True
            self.status_changed.emit("En Espera")
            self.log_message.emit(f"{self.service_name}: Esperando porque la ruta {self.local_dir} está ocupada.")
            return

        self.is_waiting = False

        cmd = ["rclone", "bisync", self.local_dir, self.remote_dir, "--verbose", "--checksum"]
        exclusions_str = conf.get("exclusions", "")
        if exclusions_str:
            for pattern in exclusions_str.splitlines():
                if pattern.strip():
                    cmd.extend(["--exclude", pattern.strip()])

        if force_resync or self.force_resync_next:
            if "--resync" not in cmd:
                cmd.append("--resync")
            self.force_resync_next = False
            self.log_message.emit(f"{self.service_name}: Re-sincronización forzada activada.")

        self.start_process(cmd)

    def force_resync(self):
        if self.is_running:
            self.force_resync_next = True
            self.log_message.emit(f"{self.service_name}: Re-sincronización programada al finalizar.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def start_process(self, cmd_list):
        self.is_running = True
        self.current_cmd = cmd_list
        self.needs_resync = False
        self.status_changed.emit("Sincronizando...")
        self.log_message.emit(f"{self.service_name}: Iniciando sincronización...")

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
                self.log_message.emit(f"[{self.service_name}] {clean_line}")
                self.check_resync_trigger(clean_line)
                self.check_prompt(clean_line)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode()
        for line in data.splitlines():
            clean_line = self.clean_log(line)
            if not clean_line:
                continue
            if "ERROR" in clean_line or "Failed" in clean_line:
                self.log_message.emit(f"[{self.service_name} Error] {clean_line}")
            else:
                self.log_message.emit(f"[{self.service_name}] {clean_line}")
            self.check_resync_trigger(clean_line)
            self.check_prompt(clean_line)

    def check_resync_trigger(self, line):
        triggers = ["Must run --resync", "bisync aborted", "run --resync", "critical error", "Safety abort"]
        if any(t.lower() in line.lower() for t in triggers):
            if not self.needs_resync:
                self.log_message.emit(f"{self.service_name}: Se requiere Re-sincronización (--resync).")
            self.needs_resync = True

    def check_prompt(self, line):
        if "?" in line and "[y/N]" in line:
            self.log_message.emit(f"[{self.service_name}] Confirmando prompt: {line}")
            self.process.write(b"y\n")

    def clean_log(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text).strip()

    def process_finished(self, exit_code, exit_status):
        self.is_running = False
        timestamp = int(datetime.now().timestamp())

        if self.local_dir:
            self.coordinator.release_lock(self.local_dir)

        if self.needs_resync:
            if "--resync" in self.current_cmd:
                self.log_message.emit(f"{self.service_name}: Falló la recuperación (--resync). Se reintentará luego.")
                self.needs_resync = False
            else:
                self.log_message.emit(f"{self.service_name}: Ejecutando auto-recuperación (--resync)...")
                cmd_copy = list(self.current_cmd)
                if "--resync" not in cmd_copy:
                    cmd_copy.append("--resync")
                self.start_process(cmd_copy)
                return

        if self.force_resync_next:
            self.force_resync_next = False
            self.log_message.emit(f"{self.service_name}: Ejecutando re-sincronización programada...")
            self.sync(force_resync=True)
            return

        if exit_code == 0:
            self.status_changed.emit("Activo")
            self.sync_finished.emit(timestamp)
            self.log_message.emit(f"{self.service_name}: Sincronización completada.")
        else:
            self.status_changed.emit("Error")
            self.log_message.emit(f"{self.service_name}: Error (Código {exit_code}). Verifique logs.")

        self.process = None
