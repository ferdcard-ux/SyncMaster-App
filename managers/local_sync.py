# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal

from core.paths import get_rclone_binary, get_rclone_bisync_cache_dir
from managers.rclone_service import ERROR_HINTS, TRANSFERRED_FILE_PATTERN, WARNING_HINTS, ProcessWorker

logger = logging.getLogger(__name__)


class LocalSyncManager(QObject):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    sync_finished = pyqtSignal(int)
    progress_updated = pyqtSignal(str, dict)
    stats_event = pyqtSignal(str, str, str)

    def __init__(
        self,
        config_manager: Any,
        coordinator: Any,
        config_key: str = "local_sync",
        service_name: str = "Local",
        progress_key: str = "local_sync",
        services_collection_key: str | None = None,
        service_id: str | None = None,
    ) -> None:
        """Initialize the local sync manager.

        Args:
            config_manager: Application configuration manager.
            coordinator: SyncCoordinator for path locking.
            config_key: Top-level config key for this service.
            service_name: Display name for log messages.
            progress_key: Key used to identify the UI progress widget.
            services_collection_key: Config key for a list of services (for multi-instance).
            service_id: Identifier within the services collection.
        """
        super().__init__()
        self.config_manager: Any = config_manager
        self.coordinator: Any = coordinator
        self.config_key: str = config_key
        self.service_name: str = service_name
        self.progress_key: str = progress_key
        self.services_collection_key: str | None = services_collection_key
        self.service_id: str | None = service_id
        self.lock_owner: str = f"LocalSync:{self.service_name}"

        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.coordinator.lock_released.connect(self.on_lock_released)

        self.is_running: bool = False
        self.is_waiting: bool = False
        self.process: Any | None = None
        self.worker: ProcessWorker | None = None
        self.active_dirs: list[str] = []
        self.force_resync_next: bool = False
        self.needs_resync: bool = False
        self.last_cmd_args: list[str] = []

    def _get_config(self) -> dict[str, Any]:
        if self.services_collection_key:
            services = self.config_manager.get(self.services_collection_key, []) or []
            for service in services:
                if service.get("id") == self.service_id:
                    return service
            return {}
        return self.config_manager.get(self.config_key, {}) or {}

    def _prefix(self) -> str:
        return self.service_name

    def start_timer(self) -> None:
        """Start or restart the periodic sync timer based on local service configuration."""
        conf = self._get_config()
        enabled = conf.get("enabled", False)
        if enabled:
            interval_minutes = conf.get("interval_minutes", 15)
            self.timer.start(interval_minutes * 60 * 1000)
            if not self.is_running:
                self.status_changed.emit("Activo")
        else:
            self.timer.stop()
            self.status_changed.emit("Desactivado")

    def stop_timer(self) -> None:
        """Stop the sync timer and gracefully terminate any running worker."""
        self.timer.stop()
        if self.is_running and self.worker:
            self.worker.stop_gracefully()
        self.status_changed.emit("Detenido")

    def shutdown(self) -> None:
        """Shut down the local sync manager, releasing all locks and terminating workers."""
        self.stop_timer()
        for sync_dir in list(self.active_dirs):
            self.coordinator.release_lock(sync_dir)
        if self.worker:
            try:
                self.worker.log_line.disconnect()
                self.worker.update_ui.disconnect()
                self.worker.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            try:
                self.worker.stop_gracefully()
            except RuntimeError:
                pass
            self.worker = None
        self.is_running = False
        self.is_waiting = False
        self.active_dirs = []
        self.force_resync_next = False
        self.needs_resync = False
        self.status_changed.emit("Detenido")

    def on_lock_released(self, released_path: str) -> None:
        """Resume a waiting sync when a relevant directory lock is released.

        Args:
            released_path: Absolute path that was unlocked.
        """
        conf = self._get_config()
        dir_a = conf.get("local_dir_a")
        dir_b = conf.get("local_dir_b")
        is_relevant = (
            released_path == os.path.abspath(dir_a or "")
            or released_path == os.path.abspath(dir_b or "")
        )
        if is_relevant and self.is_waiting and not self.is_running:
            QTimer.singleShot(1000, self.sync)

    def sync(self, force_resync: bool = False) -> None:
        """Start a local-to-local synchronization run.

        Args:
            force_resync: If True, append --resync to the rclone command.
        """
        if self.is_running:
            return

        conf = self._get_config()
        dir_a = conf.get("local_dir_a")
        dir_b = conf.get("local_dir_b")

        if not dir_a or not os.path.exists(dir_a):
            self.log_message.emit(f"{self._prefix()}: Error - Directorio A no válido")
            self.status_changed.emit("Error Config")
            return

        if not dir_b or not os.path.exists(dir_b):
            self.log_message.emit(f"{self._prefix()}: Error - Directorio B no válido")
            self.status_changed.emit("Error Config")
            return

        busy_a = self.coordinator.is_path_busy(dir_a)
        busy_b = self.coordinator.is_path_busy(dir_b)
        if busy_a or busy_b:
            self.is_waiting = True
            self.status_changed.emit("En Espera")
            busy_path = dir_a if busy_a else dir_b
            self.log_message.emit(f"{self._prefix()}: Esperando porque la ruta {busy_path} está ocupada.")
            return

        self.is_waiting = False
        self.cleanup_rclone_lock_files()

        self.coordinator.acquire_lock(dir_a, self.lock_owner)
        self.coordinator.acquire_lock(dir_b, self.lock_owner)
        self.active_dirs = [dir_a, dir_b]

        mode = self._get_mode()
        cmd = self._build_rclone_command(mode, dir_a, dir_b)

        exclusions_str = conf.get("exclusions", "")
        if exclusions_str:
            for pattern in exclusions_str.splitlines():
                cleaned = pattern.strip()
                if cleaned:
                    cmd.extend(["--exclude", cleaned])

        if mode == "bisync":
            if force_resync or self.force_resync_next:
                if "--resync" not in cmd:
                    cmd.append("--resync")
                self.force_resync_next = False
                self.log_message.emit(f"{self._prefix()}: Re-sincronización forzada activada.")
        elif force_resync or self.force_resync_next:
            self.force_resync_next = False
            self.log_message.emit(
                f"{self._prefix()}: El modo actual no admite --resync; se reinicia la sincronización."
            )

        self.start_process(cmd)

    def force_resync(self) -> None:
        """Trigger an immediate resync, or schedule one if a sync is in progress."""
        if self.is_running:
            self.force_resync_next = True
            self.log_message.emit(f"{self._prefix()}: Re-sincronización programada al finalizar.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def _get_mode(self) -> str:
        return self._get_config().get("mode", "bisync")

    def _build_rclone_command(self, mode: str, src: str, dst: str) -> list[str]:
        action = "bisync"
        extras = ["--create-empty-src-dirs"]
        if mode == "copy":
            action = "copy"
        elif mode == "sync":
            action = "sync"
            extras = []

        rclone_bin = get_rclone_binary()
        cmd = [
            rclone_bin,
            action,
            src,
            dst,
            "--verbose",
            "--checksum",
            "--stats",
            "1s",
            "--stats-one-line",
            "--local-no-check-updated",
        ]
        if action != "bisync":
            cmd.append("--progress")
        if extras:
            cmd.extend(extras)
        return cmd

    def cleanup_rclone_lock_files(self) -> None:
        """Remove stale rclone lock files (.ick/.lck) from the bisync cache directory."""
        cache_dir = get_rclone_bisync_cache_dir()
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
            self.log_message.emit(
                f"{self._prefix()}: Eliminados {removed} archivos de bloqueo de Rclone (.ick/.lck)."
            )

    def clean_log(self, text: str) -> str | None:
        """Strip ANSI escape codes from a log line.

        Args:
            text: Raw log line that may contain ANSI sequences.

        Returns:
            The cleaned text, or None if the line is empty after cleaning.
        """
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        text = ansi_escape.sub("", text).strip()
        if not text:
            return None
        return text

    def check_resync_trigger(self, line: str) -> None:
        """Check if an output line indicates a --resync is required.

        Args:
            line: A cleaned line of rclone output.
        """
        triggers = ["Must run --resync", "use --resync", "Safety abort"]
        if any(trigger in line for trigger in triggers):
            self.log_message.emit(
                f"{self._prefix()}: Detectado error de seguridad/historial. Se requiere Re-sincronización."
            )
            self.needs_resync = True

    def start_process(self, cmd_list: list[str]) -> None:
        """Launch a ProcessWorker to execute the given rclone command.

        Args:
            cmd_list: Full command-line arguments for rclone.
        """
        self.is_running = True
        self.needs_resync = False
        self.last_cmd_args = list(cmd_list)
        self.status_changed.emit("Sincronizando")
        self.log_message.emit(f"{self._prefix()}: Iniciando sincronización...")

        if self.worker:
            try:
                self.worker.log_line.disconnect()
                self.worker.update_ui.disconnect()
                self.worker.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            try:
                self.worker.stop_gracefully()
            except (RuntimeError, TypeError):
                pass
            self.worker = None

        self.worker = ProcessWorker(self.service_name, self.progress_key, cmd_list)
        self.worker.log_line.connect(self._on_worker_line, Qt.ConnectionType.QueuedConnection)
        self.worker.update_ui.connect(self._on_worker_update, Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self._on_worker_finished, Qt.ConnectionType.QueuedConnection)
        self.worker.start()

    def _on_worker_line(self, _service_name: str, line: str) -> None:
        clean = self.clean_log(line)
        if not clean:
            return
        self._emit_stats_event(clean)
        if "ERROR" in clean or "Failed" in clean:
            self.log_message.emit(f"[{self.service_name} Error] {clean}")
        else:
            self.log_message.emit(f"[{self.service_name}] {clean}")
        self.check_resync_trigger(clean)

    def _emit_stats_event(self, line: str) -> None:
        """Classify a verbose log line and emit a stats event for the counters."""
        match = TRANSFERRED_FILE_PATTERN.search(line)
        if match:
            self.stats_event.emit(self.progress_key, "completed", match.group(1).strip())
            return
        lower = line.lower()
        if any(hint in lower for hint in ERROR_HINTS):
            if "errors:" not in lower:
                self.stats_event.emit(self.progress_key, "critical", line)
        elif any(hint in lower for hint in WARNING_HINTS):
            self.stats_event.emit(self.progress_key, "warnings", line)

    def _on_worker_update(self, service_key: str, percent: int, event_type: str) -> None:
        payload = {"percent": percent, "event": event_type}
        self.progress_updated.emit(service_key, payload)

    def _on_worker_finished(self, exit_code: int) -> None:
        self.process_finished(exit_code, None)

    def process_finished(self, exit_code: int, exit_status: int | None) -> None:
        """Handle completion of the rclone subprocess.

        Args:
            exit_code: The exit code returned by the process.
            exit_status: Process exit status (unused, kept for interface compatibility).
        """
        del exit_status
        self.is_running = False
        timestamp = int(datetime.now().timestamp())

        for sync_dir in self.active_dirs:
            self.coordinator.release_lock(sync_dir)
        self.active_dirs = []

        if self.needs_resync:
            self.log_message.emit(f"{self._prefix()}: Ejecutando --resync de recuperación...")
            new_cmd = list(self.last_cmd_args) + ["--resync"]
            self.start_process(new_cmd)
            return

        if self.force_resync_next:
            self.force_resync_next = False
            self.log_message.emit(f"{self._prefix()}: Ejecutando re-sincronización programada...")
            self.sync(force_resync=True)
            return

        if exit_code == 0:
            self.status_changed.emit("Activo")
            self.sync_finished.emit(timestamp)
            self.log_message.emit(f"{self._prefix()}: Sincronización completada.")
        else:
            self.status_changed.emit("Error")
            self.log_message.emit(f"{self._prefix()}: Finalizado con Error (Código {exit_code}).")
            self.log_message.emit(
                f"{self._prefix()}: Revise el log para detalles específicos de 'rclone bisync'."
            )

        self.process = None
        self.worker = None
