# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.
from __future__ import annotations

import logging
import os
import re
import socket
import subprocess
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, QProcess, Qt, QTimer, pyqtSignal

from core.paths import get_mount_dir, get_rclone_binary
from managers.rclone_service import (
    CREDENTIAL_ERROR_PATTERNS,
    ERROR_HINTS,
    RATE_LEVELS,
    STATS_NOISE_PATTERN,
    TRANSFERRED_FILE_PATTERN,
    WARNING_HINTS,
    ProcessWorker,
    cloud_rate_flags,
    quota_detected,
)

logger = logging.getLogger(__name__)

class GDriveManager(QObject):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    sync_finished = pyqtSignal(int)
    progress_updated = pyqtSignal(str, dict)
    credential_error = pyqtSignal(str)
    quota_updated = pyqtSignal(str, dict)
    mount_changed = pyqtSignal(str, bool)
    stats_event = pyqtSignal(str, str, str)

    def __init__(self, config_manager: Any, coordinator: Any) -> None:
        """Initialize the Google Drive sync manager.

        Args:
            config_manager: Application configuration manager.
            coordinator: SyncCoordinator for path locking.
        """
        super().__init__()
        self.config_manager = config_manager
        self.coordinator = coordinator
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.coordinator.lock_released.connect(self.on_lock_released)
        self.process: subprocess.Popen | None = None
        self.worker: ProcessWorker | None = None
        self.is_running: bool = False
        self.is_waiting: bool = False
        self.local_dir: str | None = None
        self.remote_dir: str | None = None
        self.force_resync_next: bool = False
        self.dedupe_process: QProcess | None = None
        self.is_deduping: bool = False
        self._mounted: bool = False
        self._mount_process: subprocess.Popen[str] | None = None

        # Auto-ajuste de ritmo por saturación de API.
        self.rate_level = 0
        try:
            self.rate_level = max(
                0, min(int(self.config_manager.get("gdrive", {}).get("rate_limits", {}).get("level", 0)), len(RATE_LEVELS) - 1)
            )
        except (TypeError, ValueError):
            self.rate_level = 0
        self._quota_triggered = False
        self._rate_retry_timer = QTimer(self)
        self._rate_retry_timer.setSingleShot(True)
        self._rate_retry_timer.timeout.connect(self._retry_after_rate_reduction)

    @property
    def is_mounted(self) -> bool:
        return self._mounted

    @staticmethod
    def _is_mount_point(path: str) -> bool:
        try:
            result = subprocess.run(
                ["mountpoint", "-q", path],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return os.path.ismount(path)
        except subprocess.TimeoutExpired:
            return False

    def mount(self) -> None:
        if self._mounted:
            self.log_message.emit("GDrive: Ya está montado.")
            return
        remote_dir = self.config_manager.get("gdrive", {}).get("remote_dir", "")
        if not remote_dir:
            self.log_message.emit("GDrive: Error - No se puede montar sin directorio remoto configurado.")
            return
        mount_point = get_mount_dir("gdrive")
        if self._is_mount_point(mount_point):
            self._mounted = True
            self.mount_changed.emit("gdrive", True)
            self.log_message.emit(f"GDrive: El punto de montaje ya estaba activo en {mount_point}")
            return
        rclone_bin = get_rclone_binary()
        cmd = [
            rclone_bin, "mount", remote_dir, mount_point,
            "--daemon",
            "--vfs-cache-mode", "writes",
            "--dir-cache-time", "1h",
            "--log-level", "INFO",
        ]
        self.log_message.emit(f"GDrive: Montando {remote_dir} en {mount_point}...")
        self.log_message.emit(f"GDrive: Comando: {' '.join(cmd)}")
        try:
            timeout = 30
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.stderr.strip():
                self.log_message.emit(f"GDrive: stderr del mount: {result.stderr.strip()[:500]}")
            if result.returncode != 0:
                self.log_message.emit(
                    f"GDrive: Error al montar (código {result.returncode}): {result.stderr.strip()}"
                )
                return
            import time
            max_wait = 8
            for attempt in range(max_wait):
                time.sleep(1)
                if self._is_mount_point(mount_point):
                    self._mounted = True
                    self.mount_changed.emit("gdrive", True)
                    self.log_message.emit(
                        f"GDrive: Montado correctamente en {mount_point} "
                        f"(verificado en {attempt + 1}s)"
                    )
                    return
            self.log_message.emit(
                f"GDrive: Comando mount ejecutado (código {result.returncode}) "
                f"pero el punto de montaje no se activó tras {max_wait}s."
            )
        except FileNotFoundError:
            self.log_message.emit("GDrive: rclone no encontrado.")
        except subprocess.TimeoutExpired:
            self.log_message.emit("GDrive: Tiempo de espera agotado al montar.")

    def unmount(self) -> None:
        mount_point = get_mount_dir("gdrive")
        if not self._mounted and not self._is_mount_point(mount_point):
            self.log_message.emit("GDrive: No está montado.")
            return
        self._mounted = True
        import shutil
        fusermount = shutil.which("fusermount") or shutil.which("fusermount3")
        if fusermount:
            cmd = [fusermount, "-uz", mount_point]
        else:
            cmd = ["umount", mount_point]
        self.log_message.emit(f"GDrive: Desmontando {mount_point}...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                self._mounted = False
                self.mount_changed.emit("gdrive", False)
                self.log_message.emit("GDrive: Desmontado correctamente.")
            else:
                error_msg = result.stderr.strip()
                if "not mounted" in error_msg.lower():
                    self._mounted = False
                    self.mount_changed.emit("gdrive", False)
                    self.log_message.emit("GDrive: El punto de montaje ya estaba desmontado.")
                else:
                    self.log_message.emit(
                        f"GDrive: Error al desmontar (código {result.returncode}): {error_msg}"
                    )
        except FileNotFoundError:
            self.log_message.emit("GDrive: fusermount/umount no encontrado.")
        except subprocess.TimeoutExpired:
            self.log_message.emit("GDrive: Tiempo de espera agotado al desmontar.")

    def start_timer(self) -> None:
        """Start or restart the periodic sync timer based on gdrive configuration."""
        enabled = self.config_manager.get("gdrive", {}).get("enabled", False)
        if enabled:
            interval_minutes = self.config_manager.get("gdrive", {}).get("interval_minutes", 15)
            self.timer.start(interval_minutes * 60 * 1000)
            if not self.is_running:
                self.status_changed.emit("Activo")
                self.fetch_quota()
        else:
            self.timer.stop()
            self.status_changed.emit("Desactivado")

    def fetch_quota(self) -> None:
        """Fetch Google Drive storage quota information asynchronously."""
        remote_dir = self.config_manager.get("gdrive", {}).get("remote_dir", "")
        remote = remote_dir.split(":")[0].strip() if remote_dir else ""
        if not remote:
            return
        import threading
        def _do_fetch():
            try:
                cmd = [get_rclone_binary(), "about", "--json", f"{remote}:"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if result.returncode == 0 and result.stdout.strip():
                    import json as _json
                    data = _json.loads(result.stdout)
                    quota = {}
                    for key in ("total", "used", "free", "trashed"):
                        if key in data:
                            quota[key] = data[key]
                    if quota:
                        self.quota_updated.emit("gdrive", quota)
            except Exception:
                logger.warning("fetch_quota failed for gdrive", exc_info=True)
        threading.Thread(target=_do_fetch, daemon=True).start()

    def stop_timer(self) -> None:
        """Stop the sync timer and gracefully terminate any running workers."""
        self.timer.stop()
        self._rate_retry_timer.stop()
        if self.worker:
            try:
                self.worker.stop_gracefully()
            except RuntimeError:
                pass
        if self.dedupe_process and self.dedupe_process.state() != QProcess.ProcessState.NotRunning:
            self.dedupe_process.terminate()
            if not self.dedupe_process.waitForFinished(3000):
                self.dedupe_process.kill()

    def shutdown(self) -> None:
        """Shut down the GDrive manager, releasing locks and terminating all processes."""
        self.timer.stop()
        self._rate_retry_timer.stop()
        if self._mounted:
            self.unmount()
        if self.local_dir:
            self.coordinator.release_lock(self.local_dir)
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
        if self.dedupe_process:
            self.dedupe_process.terminate()
            if not self.dedupe_process.waitForFinished(5000):
                self.dedupe_process.kill()
                self.dedupe_process.waitForFinished(2000)
            self.dedupe_process = None
        self.is_running = False
        self.is_waiting = False
        self.is_deduping = False
        self.force_resync_next = False
        self.local_dir = None
        self.process = None
        self.status_changed.emit("Detenido")

    def on_lock_released(self, released_path: str) -> None:
        """Resume a waiting sync when the GDrive local directory lock is released.

        Args:
            released_path: Absolute path that was unlocked.
        """
        local_dir = self.config_manager.get("gdrive", {}).get("local_dir")
        if local_dir and released_path == os.path.abspath(local_dir) and self.is_waiting and not self.is_running:
            QTimer.singleShot(1000, self.sync)

    def check_connectivity(self) -> bool:
        """Check network connectivity to Google API servers.

        Returns:
            True if a TCP connection to googleapis.com succeeds.
        """
        try:
            socket.create_connection(("www.googleapis.com", 443), timeout=5)
            return True
        except (TimeoutError, OSError):
            return False

    def sync(self, force_resync: bool = False) -> None:
        """Start a Google Drive synchronization run.

        Args:
            force_resync: If True, append --resync to the rclone command.
        """
        if self.is_running or self.is_deduping:
            return

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

        if not self.coordinator.acquire_lock(self.local_dir, "GDrive"):
            self.is_waiting = True
            self.status_changed.emit("En Espera")
            self.log_message.emit(f"GDrive: Esperando porque la ruta {self.local_dir} está ocupada.")
            return

        self.is_waiting = False

        mode = self._get_mode()
        cmd = self._build_rclone_command(mode, self.local_dir, self.remote_dir)
        exclusions_str = self.config_manager.get("gdrive", {}).get("exclusions", "")
        if exclusions_str:
            for pattern in exclusions_str.splitlines():
                if pattern.strip():
                    cmd.extend(["--exclude", pattern.strip()])

        if mode == "bisync":
            if force_resync or self.force_resync_next:
                if "--resync" not in cmd:
                    cmd.append("--resync")
                self.force_resync_next = False
                self.log_message.emit("GDrive: Re-sincronización forzada activada.")
        else:
            if force_resync or self.force_resync_next:
                self.force_resync_next = False
                self.log_message.emit("GDrive: El modo seleccionado no admite --resync; se reinicia la sincronización.")

        self.start_process(cmd)

    def force_resync(self) -> None:
        """Trigger an immediate resync, or schedule one if a sync is in progress."""
        if self.is_running or self.is_deduping:
            self.force_resync_next = True
            self.log_message.emit("GDrive: Re-sincronización programada al finalizar.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def _get_mode(self) -> str:
        return self.config_manager.get("gdrive", {}).get("mode", "bisync")

    def _build_rclone_command(self, mode: str, src: str, dst: str) -> list[str]:
        action = "bisync"
        extras = []
        if mode == "copy":
            action = "copy"
            extras = ["--create-empty-src-dirs"]
        elif mode == "sync":
            action = "sync"
        rclone_bin = get_rclone_binary()
        cmd = [
            rclone_bin, action, src, dst, "--verbose", "--checksum",
            "--stats", "5s", "--stats-one-line", "--local-no-check-updated"
        ]
        if action != "bisync":
            cmd.append("--progress")
        cmd.extend(cloud_rate_flags(self.rate_level))
        cmd.extend(extras)
        return cmd

    def start_process(self, cmd_list: list[str]) -> None:
        """Launch a ProcessWorker to execute the given rclone command.

        Args:
            cmd_list: Full command-line arguments for rclone.
        """
        self.is_running = True
        self.current_cmd = cmd_list
        self.needs_resync = False
        self.status_changed.emit("Sincronizando")
        self.log_message.emit("GDrive: Iniciando sincronización...")

        if self.worker:
            try:
                self.worker.log_line.disconnect()
                self.worker.update_ui.disconnect()
                self.worker.finished.disconnect()
            except (RuntimeError, TypeError):
                pass
            self.worker.stop_gracefully()

        self.worker = ProcessWorker("GDrive", "gdrive", cmd_list)
        self.worker.log_line.connect(self._on_worker_line, Qt.ConnectionType.QueuedConnection)
        self.worker.update_ui.connect(self._on_worker_update, Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self._on_worker_finished, Qt.ConnectionType.QueuedConnection)
        self.worker.start()

    def _on_worker_line(self, _svc: str, line: str) -> None:
        clean = self.clean_log(line)
        if not clean:
            return
        if STATS_NOISE_PATTERN.match(clean):
            return
        self._emit_stats_event(clean)
        if quota_detected(clean):
            self._handle_quota_detected()
        if "ERROR" in clean or "Failed" in clean:
            network_errors = ["network is unreachable", "connection refused", "timeout", "SSL connect error"]
            if any(e.lower() in clean.lower() for e in network_errors):
                self.log_message.emit(f"[GDrive Red] {clean}")
                self.status_changed.emit("Sin Conexión")
            else:
                self.log_message.emit(f"[GDrive Error] {clean}")
        else:
            self.log_message.emit(f"[GDrive] {clean}")
        self.check_resync_trigger(clean)
        self.check_prompt(clean)
        if any(p in clean.lower() for p in CREDENTIAL_ERROR_PATTERNS):
            self.credential_error.emit(f"GDrive: {clean}")

    def _emit_stats_event(self, line: str) -> None:
        """Classify a verbose log line and emit a stats event for the counters."""
        match = TRANSFERRED_FILE_PATTERN.search(line)
        if match:
            self.stats_event.emit("gdrive", "completed", match.group(1).strip())
            return
        lower = line.lower()
        if any(hint in lower for hint in ERROR_HINTS):
            if "errors:" not in lower:
                self.stats_event.emit("gdrive", "critical", line)
        elif any(hint in lower for hint in WARNING_HINTS):
            self.stats_event.emit("gdrive", "warnings", line)

    def _persist_rate_level(self) -> None:
        gdrive_conf = self.config_manager.get("gdrive", {}) or {}
        gdrive_conf["rate_limits"] = {"level": self.rate_level}
        self.config_manager.set("gdrive", gdrive_conf)

    def _handle_quota_detected(self) -> None:
        if self._quota_triggered:
            return
        if self.rate_level < len(RATE_LEVELS) - 1:
            self.rate_level += 1
            self._persist_rate_level()
            self._quota_triggered = True
            self.status_changed.emit("Ritmo reducido")
            self.log_message.emit(
                f"GDrive: API Saturada. Reduciendo ritmo de transferencia "
                f"(nivel {self.rate_level}). Reintentando en 2 minutos..."
            )
            if self.worker:
                try:
                    self.worker.stop_gracefully()
                except RuntimeError:
                    pass
            self._rate_retry_timer.start(2 * 60 * 1000)

    def _retry_after_rate_reduction(self) -> None:
        self._quota_triggered = False
        self.status_changed.emit("Activo")
        self.log_message.emit(f"GDrive: Reintentando con ritmo reducido (nivel {self.rate_level})...")
        self.sync()

    def _on_worker_update(self, service_key: str, percent: int, event_type: str) -> None:
        payload = {"percent": percent, "event": event_type}
        self.progress_updated.emit(service_key, payload)

    def _on_worker_finished(self, exit_code: int) -> None:
        return self.process_finished(exit_code, None)

    def check_resync_trigger(self, line: str) -> None:
        """Check if an output line indicates a --resync is required.

        Args:
            line: A cleaned line of rclone output.
        """
        network_errors = ["network is unreachable", "connection refused", "timeout", "SSL connect error", "failed to create file system"]
        if any(e.lower() in line.lower() for e in network_errors):
            self.needs_resync = False
            return

        triggers = ["Must run --resync", "bisync aborted", "run --resync", "critical error"]
        if any(t.lower() in line.lower() for t in triggers):
            if not self.needs_resync:
                self.log_message.emit("GDrive: Detectado error crítico de historial. Se requiere Re-sincronización (--resync).")
            self.needs_resync = True

    def check_prompt(self, line: str) -> None:
        """Auto-confirm interactive y/n prompts from rclone.

        Args:
            line: A cleaned line of rclone output.
        """
        if "?" in line and "[y/N]" in line:
             self.log_message.emit(f"[GDrive] Confirmando prompt: {line}")
             if self.worker:
                 self.worker.send_input("y\n")

    def clean_log(self, text: str) -> str:
        """Strip ANSI escape codes from a log line.

        Args:
            text: Raw log line that may contain ANSI sequences.

        Returns:
            The cleaned text with ANSI codes removed.
        """
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text).strip()

    def process_finished(self, exit_code: int, timestamp: int | None) -> None:
        """Handle completion of the rclone subprocess.

        Args:
            exit_code: The exit code returned by the process.
            timestamp: Optional timestamp (unused, kept for interface compatibility).
        """
        self.is_running = False
        timestamp = int(datetime.now().timestamp())

        if self.local_dir:
            self.coordinator.release_lock(self.local_dir)

        if self.needs_resync:
            if "--resync" in self.current_cmd:
                self.log_message.emit("GDrive: Falló la actualización crítica (--resync). Se reintentará en el próximo intervalo.")
                self.needs_resync = False
            else:
                if self.check_connectivity():
                    self.log_message.emit("GDrive: Ejecutando auto-recuperación (--resync)...")
                    cmd_copy = list(self.current_cmd)
                    if "--resync" not in cmd_copy:
                        cmd_copy.append("--resync")
                    self.start_process(cmd_copy)
                    return
                else:
                    self.log_message.emit("GDrive: Error crítico de historial, pero no hay conexión para recuperar. Esperando...")
                    self.needs_resync = True
        if self.force_resync_next:
            self.force_resync_next = False
            self.log_message.emit("GDrive: Ejecutando re-sincronización programada...")
            self.sync(force_resync=True)
            return

        if exit_code == 0:
            if self._quota_triggered:
                self.status_changed.emit("Limitado (API)")
                self.log_message.emit("GDrive: Saturación de API detectada. Reintentando con ritmo reducido.")
            else:
                if self.rate_level > 0:
                    self.rate_level -= 1
                    self._persist_rate_level()
                    self.log_message.emit(f"GDrive: Sincronización exitosa. Ritmo recuperado (nivel {self.rate_level}).")
                self.status_changed.emit("Activo")
                self.sync_finished.emit(timestamp)
                self.fetch_quota()
                self.log_message.emit("GDrive: Sincronización completada.")
                if self.config_manager.get("gdrive", {}).get("auto_dedupe", True):
                    self.start_dedupe()
        else:
            if self._quota_triggered:
                self.status_changed.emit("Limitado (API)")
            else:
                self.status_changed.emit("Error")
                self.log_message.emit(f"GDrive: Error (Código {exit_code}). Verifique logs.")

        self.process = None

    def start_dedupe(self) -> None:
        """Start an automatic rclone dedupe process on the remote drive."""
        if self.is_deduping or not self.remote_dir:
            return

        self.is_deduping = True
        self.log_message.emit("GDrive: Iniciando deduplicación automática (rclone dedupe)...")

        cmd = [get_rclone_binary(), "dedupe", "--dedupe-mode", "newest", "--verbose", self.remote_dir]

        self.dedupe_process = QProcess()
        self.dedupe_process.readyReadStandardOutput.connect(self.handle_dedupe_stdout)
        self.dedupe_process.readyReadStandardError.connect(self.handle_dedupe_stderr)
        self.dedupe_process.finished.connect(self.dedupe_finished)
        self.dedupe_process.start(cmd[0], cmd[1:])

    def handle_dedupe_stdout(self) -> None:
        """Read and emit dedupe process stdout lines to the log."""
        data = self.dedupe_process.readAllStandardOutput().data().decode()
        for line in data.splitlines():
            clean_line = self.clean_log(line)
            if clean_line:
                self.log_message.emit(f"[GDrive Dedupe] {clean_line}")

    def handle_dedupe_stderr(self) -> None:
        """Read and emit dedupe process stderr lines to the log."""
        data = self.dedupe_process.readAllStandardError().data().decode()
        for line in data.splitlines():
            clean_line = self.clean_log(line)
            if clean_line:
                self.log_message.emit(f"[GDrive Dedupe] {clean_line}")

    def dedupe_finished(self, exit_code: int, exit_status: Any) -> None:
        """Handle completion of the dedupe process.

        Args:
            exit_code: The exit code returned by the dedupe process.
            exit_status: Process exit status from QProcess.
        """
        self.is_deduping = False
        if exit_code == 0:
            self.log_message.emit("GDrive: Deduplicación finalizada correctamente.")
        else:
            self.log_message.emit(f"GDrive: Deduplicación finalizó con error (Código {exit_code}).")
        self.dedupe_process = None
