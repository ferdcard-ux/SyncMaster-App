# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import traceback
from datetime import datetime
from typing import Any

# Sync Master Rclone service manager.
# Copyright 2026 FerDev
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal

from core.paths import get_mount_dir, get_rclone_binary, get_rclone_bisync_cache_dir, get_rclone_filters_path

logger = logging.getLogger(__name__)

PROGRESS_PATTERN = re.compile(r"(\d+)\s*%", re.IGNORECASE)
SPEED_PATTERN = re.compile(r"(\d+(?:\.\d+)?\s*[KMGT]?i?B/s)", re.IGNORECASE)
ETA_PATTERN = re.compile(r"ETA\s*([^,\s]+)", re.IGNORECASE)

# Líneas de estadísticas de rclone sin transferencia activa (p. ej. "0 B / 0 B, -, 0 B/s, ETA -").
# Se filtran para no ensuciar los registros detallados del usuario.
STATS_NOISE_PATTERN = re.compile(
    r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\s+\S+\s*:\s*\d+\s*[KMG]?i?B\s*/\s*\d+\s*[KMG]?i?B\s*,\s*-\s*,\s*0\s*[KMG]?i?B/s\s*,\s*ETA\s*-\s*$"
)

# Líneas verbose de rclone que indican que un archivo se transfirió con éxito.
# Formato: "2026/07/16 10:00:00 INFO  : subdir/archivo.txt: Copied (new)"
TRANSFERRED_FILE_PATTERN = re.compile(
    r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2}\s+(?:INFO|NOTICE|DEBUG)\s*:\s+(.+?):\s+(?:Copied|Updated|Moved|Renamed)\b(?!\s+to\s+trash)",
    re.IGNORECASE,
)

# Claves de advertencia/error para clasificar líneas en el panel de estadísticas.
WARNING_HINTS = ("notice", "warning", "retry", "retrying", "retry after")
ERROR_HINTS = ("error", "failed", "panic", "critical error")

# Patrones de saturación de API que disparan el auto-ajuste de ritmo.
# Se detecta específicamente "(Error 403: Quota exceeded" y variantes del proveedor.
QUOTA_PATTERNS = [
    "quota exceeded",
    "error 403",
    "403: quota",
    "user rate limit exceeded",
    "rate limit exceeded",
    "error 429",
    "too many requests",
]

# Niveles de ritmo de transferencia (de normal a máxima reducción).
RATE_LEVELS: list[dict[str, int]] = [
    {"transfers": 2, "checkers": 4, "tpslimit": 5},  # nivel 0: normal
    {"transfers": 1, "checkers": 2, "tpslimit": 3},  # nivel 1
    {"transfers": 1, "checkers": 1, "tpslimit": 1},  # nivel 2: máxima reducción
]


def cloud_rate_flags(level: int) -> list[str]:
    """Return rclone concurrency flags for the given rate level.

    Args:
        level: Rate level index, clamped to the valid range.

    Returns:
        List of rclone flags, e.g. ``["--transfers", "2", ...]``.
    """
    clamped = max(0, min(level, len(RATE_LEVELS) - 1))
    cfg = RATE_LEVELS[clamped]
    return ["--transfers", str(cfg["transfers"]), "--checkers", str(cfg["checkers"]), "--tpslimit", str(cfg["tpslimit"])]


def quota_detected(text: str) -> bool:
    """Check whether a log line indicates an API quota/rate limit error.

    Args:
        text: Cleaned log line from rclone.

    Returns:
        True if the line matches a known quota/rate-limit pattern.
    """
    lowered = text.lower()
    return any(p in lowered for p in QUOTA_PATTERNS)

CREDENTIAL_ERROR_PATTERNS = [
    "couldn't login",
    "invalid credentials",
    "invalid authentication",
    "unauthorized",
    "access denied",
    "token expired",
    "invalid_grant",
    "invalid_refresh_token",
    "couldn't find section in config file",
    "couldn't find",
    "404 not found",
    "http 404",
    "authentication failed",
    "login failed",
    "permission denied",
    "invalid login",
    "bad password",
    "wrong password",
]


class ProcessWorker(QThread):
    log_line = pyqtSignal(str, str)
    update_ui = pyqtSignal(str, int, str)
    finished = pyqtSignal(int)

    PROGRESS_REGEX = re.compile(r"(\d+)\s*%", re.IGNORECASE)
    START_KEYWORDS = ["scanning", "init", "starting", "preparing", "queueing"]

    def __init__(self, service_name: str, widget_key: str, cmd_list: list[str]) -> None:
        """Initialize a worker thread to run an rclone subprocess.

        Args:
            service_name: Display name of the associated service.
            widget_key: Key used to identify the UI progress widget.
            cmd_list: Command and arguments to execute.
        """
        super().__init__()
        self.service_name = service_name
        self.widget_key = widget_key
        self.cmd_list = list(cmd_list)
        self._stop_requested = False
        self._process: subprocess.Popen[str] | None = None
        self._last_overall_percent = 0

    def run(self) -> None:
        """Execute the subprocess and stream its output until completion."""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        kwargs: dict[str, Any] = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
            encoding="utf-8",
            env=env,
        )
        try:
            self._process = subprocess.Popen(self.cmd_list, **kwargs)
        except Exception as exc:
            self.log_line.emit(self.service_name, f"Error al iniciar rclone: {exc}")
            self.finished.emit(1)
            return

        try:
            while True:
                if self._stop_requested:
                    break
                try:
                    line = self._process.stdout.readline()
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    logging.error(f"Error leyendo salida de proceso ({self.service_name}): {e}")
                    break

                if line == "" and self._process.poll() is not None:
                    break
                if not line:
                    continue

                clean_line = line.strip()
                if not clean_line:
                    continue

                self.log_line.emit(self.service_name, clean_line)
                self._emit_status(clean_line)

                if "[y/n]" in clean_line.lower() or "[y/N]" in clean_line:
                    self.send_input("y\n")
        except Exception as outer_exc:
            logging.critical(f"Error crítico en hilo de ProcessWorker ({self.service_name}): {outer_exc}")
            logging.critical(traceback.format_exc())
        finally:
            if self._process:
                exit_code = self._process.wait()
                self.finished.emit(exit_code if exit_code is not None else 1)
            else:
                self.finished.emit(1)

    def send_input(self, payload: str) -> None:
        """Write data to the subprocess stdin.

        Args:
            payload: The string to send to the process.
        """
        if self._process and self._process.stdin:
            try:
                self._process.stdin.write(payload)
                self._process.stdin.flush()
            except Exception:
                logger.debug("send_input failed for %s", self.service_name)

    def stop(self) -> None:
        """Request the subprocess to terminate."""
        self._stop_requested = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                logger.debug("stop failed for %s", self.service_name)

    def stop_gracefully(self, timeout_ms: int = 5000) -> bool:
        """Terminate the process gracefully, escalating to kill if needed.

        Args:
            timeout_ms: Milliseconds to wait before force-killing the process.

        Returns:
            True if the process exited within the timeout.
        """
        self.stop()
        if self.wait_safe(timeout_ms):
            return True
        if self._process and self._process.poll() is None:
            try:
                self._process.kill()
            except Exception:
                pass
        return self.wait_safe(2000)

    def __del__(self):
        if not self.isRunning():
            return
        try:
            self.stop()
            self.wait_safe(2000)
        except RuntimeError:
            pass

    def wait_safe(self, msecs: int = 0) -> bool:
        """Wait for the thread to finish, avoiding deadlocks from self-re-entry.

        Args:
            msecs: Maximum milliseconds to wait (0 = indefinite).

        Returns:
            True if the thread finished within the timeout.
        """
        if QThread.currentThread() == self:
            logging.debug(f"ProcessWorker ({self.service_name}): evitada espera del hilo sobre sí mismo (re-entrada detectada).")
            return False
        return super().wait(msecs)

    def _emit_status(self, line: str) -> None:
        percent = self._extract_percent(line)
        event_type = self._determine_event_type(line)
        if percent is not None:
            if percent > 0 or self._last_overall_percent == 0:
                self._last_overall_percent = percent
                self.update_ui.emit(self.widget_key, percent, event_type)
        elif event_type != "progress":
            self.update_ui.emit(self.widget_key, self._last_overall_percent, event_type)

    def _extract_percent(self, line: str) -> int | None:
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                payload = json.loads(stripped)
                value = payload.get("percent") or payload.get("progress") or payload.get("percentage")
                if value is not None:
                    return int(float(value))
            except ValueError:
                pass
        match = self.PROGRESS_REGEX.search(line)
        if match:
            return int(match.group(1))
        return None

    def _determine_event_type(self, line: str) -> str:
        lower = line.lower()
        if "error" in lower or "failed" in lower:
            if lower.startswith("errors:"):
                try:
                    after_colon = lower.split(":", 1)[1].strip()
                    if after_colon.replace(",", "").strip() == "0":
                        return "progress"
                except (IndexError, ValueError):
                    pass
            return "error"
        if "notice" in lower or "retry" in lower:
            return "warning"
        if any(keyword in lower for keyword in self.START_KEYWORDS):
            return "start"
        if "transferred" in lower or "transferring" in lower or "%" in lower:
            return "progress"
        return "progress"


class RcloneServiceManager(QObject):
    status_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    sync_finished = pyqtSignal(int)
    progress_updated = pyqtSignal(str, dict)
    credential_error = pyqtSignal(str)
    quota_updated = pyqtSignal(str, dict)
    mount_changed = pyqtSignal(str, bool)
    stats_event = pyqtSignal(str, str, str)

    CLOUD_CONCURRENCY_FLAGS = ["--transfers", "2", "--checkers", "4", "--tpslimit", "5"]
    DRIVE_CHUNK_FLAG = ["--drive-chunk-size", "64M"]
    CLOUD_KEYWORDS = ["drive", "mega", "onedrive", "cloud", "s3", "ws", "ftp", "dropbox"]

    def __init__(self, config_manager: Any, coordinator: Any, service_name: str) -> None:
        """Initialize the rclone service manager for a named service.

        Args:
            config_manager: Application configuration manager.
            coordinator: SyncCoordinator for path locking.
            service_name: Identifier of the rclone service to manage.
        """
        super().__init__()
        self.config_manager = config_manager
        self.coordinator = coordinator
        self.service_name = service_name
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.coordinator.lock_released.connect(self.on_lock_released)
        self.worker: ProcessWorker | None = None
        self._last_event_status: str | None = None
        self.progress_key = f"rclone:{self.service_name}"
        self.is_running = False
        self.is_waiting = False
        self.local_dir: str | None = None
        self.remote_dir: str | None = None
        self.needs_resync = False
        self.force_resync_next = False
        self.current_cmd: list[str] = []
        self._error_lines: list[str] = []
        self._mounted = False
        self._mount_process: subprocess.Popen[str] | None = None
        self._quota_backoff_active = False
        self._quota_triggered = False
        self._quota_backoff_timer = QTimer(self)
        self._quota_backoff_timer.setSingleShot(True)
        self._quota_backoff_timer.timeout.connect(self._release_quota_backoff)

        # Nivel de ritmo de transferencia persistido (auto-ajuste ante cuota).
        self.rate_level = 0
        conf = self._get_service_config() or {}
        rate_limits = conf.get("rate_limits") if isinstance(conf, dict) else None
        if isinstance(rate_limits, dict):
            try:
                self.rate_level = max(0, min(int(rate_limits.get("level", 0)), len(RATE_LEVELS) - 1))
            except (TypeError, ValueError):
                self.rate_level = 0

        self._wait_retry_timer = QTimer(self)
        self._wait_retry_timer.setSingleShot(True)
        self._wait_retry_timer.timeout.connect(self._retry_waiting_sync)

        self._rate_retry_timer = QTimer(self)
        self._rate_retry_timer.setSingleShot(True)
        self._rate_retry_timer.timeout.connect(self._retry_after_rate_reduction)

        self.filter_file = get_rclone_filters_path()
        self._ensure_global_filters()

    def _get_service_config(self) -> dict | None:
        services = self.config_manager.get("rclone_services", []) or []
        for service in services:
            if service.get("name") == self.service_name:
                return service
        return None

    @staticmethod
    def _extract_remote_name(remote_dir: str | None) -> str:
        if not remote_dir:
            return ""
        name = remote_dir.split(":")[0].strip()
        return name

    def fetch_quota(self) -> None:
        """Fetch remote storage quota information asynchronously in a background thread."""
        conf = self._get_service_config()
        if not conf:
            return
        remote_dir = conf.get("remote_dir", "")
        remote = self._extract_remote_name(remote_dir)
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
                        self.quota_updated.emit(self.service_name, quota)
            except Exception:
                logger.warning("fetch_quota failed for %s", self.service_name, exc_info=True)
        threading.Thread(target=_do_fetch, daemon=True).start()

    def _is_cloud_provider(self, provider_key: str | None) -> bool:
        candidate = (provider_key or self.service_name or "").lower()
        return any(keyword in candidate for keyword in self.CLOUD_KEYWORDS)

    def _apply_cloud_flags(self, cmd: list[str], provider_key: str | None) -> list[str]:
        if not self._is_cloud_provider(provider_key):
            return cmd
        candidate = (provider_key or self.service_name or "").lower()
        cmd.extend(cloud_rate_flags(self.rate_level))
        if "drive" in candidate:
            cmd.extend(self.DRIVE_CHUNK_FLAG)
            cmd.append("--drive-skip-gdocs")
        return cmd

    def _persist_rate_level(self) -> None:
        services = self.config_manager.get("rclone_services", []) or []
        for service in services:
            if service.get("name") == self.service_name:
                service["rate_limits"] = {"level": self.rate_level}
                break
        self.config_manager.set("rclone_services", services)

    def _activate_quota_backoff(self) -> None:
        if self._quota_backoff_active:
            return
        self._quota_backoff_active = True
        self._quota_triggered = True
        self.timer.stop()
        self.status_changed.emit("Limitado (API)")
        self.log_message.emit(f"[{self.service_name}] API Saturada. Entrando en modo de espera preventivo...")
        self._quota_backoff_timer.start(5 * 60 * 1000)

    def _release_quota_backoff(self) -> None:
        self._quota_backoff_active = False
        self._quota_triggered = False
        self.log_message.emit(f"{self.service_name}: Modo limitado terminado. Reanudando la programación automática.")
        conf = self._get_service_config()
        if conf and conf.get("enabled", True):
            self.status_changed.emit("Activo")
            self.start_timer()

    def _handle_quota_line(self, text: str) -> None:
        if not quota_detected(text):
            return
        if self.rate_level < len(RATE_LEVELS) - 1:
            self._reduce_rate_and_retry()
        else:
            self._activate_quota_backoff()

    def _reduce_rate_and_retry(self) -> None:
        if self._quota_backoff_active:
            return
        self.rate_level += 1
        self._persist_rate_level()
        self._quota_triggered = True
        self.timer.stop()
        self.status_changed.emit("Ritmo reducido")
        self.log_message.emit(
            f"[{self.service_name}] API Saturada. Reduciendo ritmo de transferencia "
            f"(nivel {self.rate_level}). Reintentando en 2 minutos..."
        )
        if self.worker is not None:
            try:
                self.worker.stop_gracefully()
            except RuntimeError:
                pass
        self._rate_retry_timer.start(2 * 60 * 1000)

    def _retry_waiting_sync(self) -> None:
        if not self.is_waiting:
            return
        self.log_message.emit(f"{self.service_name}: Reintentando sincronización en espera...")
        self.sync()
        if self.is_waiting:
            self._wait_retry_timer.start(5000)

    def _retry_after_rate_reduction(self) -> None:
        """Reintenta la sincronización tras haber reducido el ritmo por cuota."""
        self._quota_triggered = False
        self.status_changed.emit("Activo")
        self.log_message.emit(f"{self.service_name}: Reintentando con ritmo reducido (nivel {self.rate_level})...")
        conf = self._get_service_config()
        if conf and conf.get("enabled", True):
            self.sync()

    def _ensure_global_filters(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.filter_file), exist_ok=True)
            new_patterns = (
                "# Exclusiones estándar (Evita advertencias innecesarias)\n"
                "- .Trash-**\n"
                "- .cache/**\n"
                "- lost+found/**\n"
                "- **.tmp\n"
                "- **.bak\n"
                "- .DS_Store\n"
                "- desktop.ini\n"
                "# Evitar recursión y errores de Python en AppDirs\n"
                "- **/AppDir/usr/lib/python*/**\n"
                "# Excluir entornos virtuales y tmp Python (evita errores OneDrive API con symlinks ~)\n"
                "- **/.venv/**\n"
                "- **/venv/**\n"
                "- **/__pycache__/**\n"
                "- **/*.pyc\n"
                "- **/~*\n"
                "- **/node_modules/**\n"
            )
            if not os.path.exists(self.filter_file):
                with open(self.filter_file, "w", encoding="utf-8") as f:
                    f.write(new_patterns)
            else:
                with open(self.filter_file, encoding="utf-8") as f:
                    existing = f.read()
                missing = []
                markers = [
                    "# Excluir entornos virtuales",
                    "- **/.venv/**",
                    "- **/venv/**",
                    "- **/__pycache__/**",
                    "- **/*.pyc",
                    "- **/~*",
                    "- **/node_modules/**",
                ]
                for m in markers:
                    if m not in existing:
                        missing.append(m)
                if missing:
                    with open(self.filter_file, "a", encoding="utf-8") as f:
                        f.write("\n# Excluir entornos virtuales y tmp Python (evita errores OneDrive API con symlinks ~)\n")
                        for m in missing:
                            if not m.startswith("#"):
                                f.write(m + "\n")
                    self.log_message.emit(
                        f"{self.service_name}: Filtros globales actualizados con nuevas exclusiones."
                    )
        except Exception as e:
            print(f"Error al crear filtros globales: {e}")

    @property
    def is_mounted(self) -> bool:
        return self._mounted

    def _get_mount_remote(self) -> str | None:
        conf = self._get_service_config()
        if not conf:
            return None
        return conf.get("remote_dir") or f"{self.service_name}:"

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
            self.log_message.emit(f"{self.service_name}: Ya está montado.")
            return
        remote = self._get_mount_remote()
        if not remote:
            self.log_message.emit(f"{self.service_name}: Error - No se puede montar sin directorio remoto configurado.")
            return
        mount_point = get_mount_dir(self.service_name)
        if self._is_mount_point(mount_point):
            self._mounted = True
            self.mount_changed.emit(self.service_name, True)
            self.log_message.emit(f"{self.service_name}: El punto de montaje ya estaba activo en {mount_point}")
            return
        rclone_bin = get_rclone_binary()
        cmd = [
            rclone_bin, "mount", remote, mount_point,
            "--daemon",
            "--vfs-cache-mode", "writes",
            "--dir-cache-time", "1h",
            "--log-level", "INFO",
        ]
        candidate = (self.service_name or "").lower()
        if "mega" in candidate:
            cmd.extend(["--tpslimit", "5", "--tpslimit-burst", "10", "--mega-hard-delete"])
        self.log_message.emit(f"{self.service_name}: Montando {remote} en {mount_point}...")
        self.log_message.emit(f"{self.service_name}: Comando: {' '.join(cmd)}")
        try:
            timeout = 60 if "mega" in candidate else 30
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.stderr.strip():
                self.log_message.emit(
                    f"{self.service_name}: stderr del mount: {result.stderr.strip()[:500]}"
                )
            if result.returncode != 0:
                self.log_message.emit(
                    f"{self.service_name}: Error al montar (código {result.returncode}): {result.stderr.strip()}"
                )
                return
            import time
            max_wait = 15 if "mega" in candidate else 8
            for attempt in range(max_wait):
                time.sleep(1)
                if self._is_mount_point(mount_point):
                    self._mounted = True
                    self.mount_changed.emit(self.service_name, True)
                    self.log_message.emit(
                        f"{self.service_name}: Montado correctamente en {mount_point} "
                        f"(verificado en {attempt + 1}s)"
                    )
                    return
            self.log_message.emit(
                f"{self.service_name}: Comando mount ejecutado (código {result.returncode}) "
                f"pero el punto de montaje no se activó tras {max_wait}s. "
                f"Verifique que FUSE esté disponible y que el remote sea accesible."
            )
        except FileNotFoundError:
            self.log_message.emit(f"{self.service_name}: rclone no encontrado.")
        except subprocess.TimeoutExpired:
            self.log_message.emit(f"{self.service_name}: Tiempo de espera agotado al montar.")

    def unmount(self) -> None:
        mount_point = get_mount_dir(self.service_name)
        if not self._mounted and not self._is_mount_point(mount_point):
            self.log_message.emit(f"{self.service_name}: No está montado.")
            return
        self._mounted = True
        import shutil
        fusermount = shutil.which("fusermount") or shutil.which("fusermount3")
        if fusermount:
            cmd = [fusermount, "-uz", mount_point]
        else:
            cmd = ["umount", mount_point]
        self.log_message.emit(f"{self.service_name}: Desmontando {mount_point}...")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                self._mounted = False
                self.mount_changed.emit(self.service_name, False)
                self.log_message.emit(f"{self.service_name}: Desmontado correctamente.")
            else:
                error_msg = result.stderr.strip()
                if "not mounted" in error_msg.lower():
                    self._mounted = False
                    self.mount_changed.emit(self.service_name, False)
                    self.log_message.emit(f"{self.service_name}: El punto de montaje ya estaba desmontado.")
                else:
                    self.log_message.emit(
                        f"{self.service_name}: Error al desmontar (código {result.returncode}): {error_msg}"
                    )
        except FileNotFoundError:
            self.log_message.emit(f"{self.service_name}: fusermount/umount no encontrado.")
        except subprocess.TimeoutExpired:
            self.log_message.emit(f"{self.service_name}: Tiempo de espera agotado al desmontar.")

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
                f"{self.service_name}: Eliminados {removed} archivos de bloqueo de Rclone (.ick/.lck)."
            )

    def start_timer(self) -> None:
        """Start or restart the periodic sync timer based on the service configuration."""
        conf = self._get_service_config()
        if not conf:
            self.timer.stop()
            self.status_changed.emit("Desactivado")
            return

        if self._quota_backoff_active:
            return

        enabled = conf.get("enabled", True)
        if enabled:
            interval_minutes = conf.get("interval_minutes", 15)
            self.timer.start(interval_minutes * 60 * 1000)
            if not self.is_running:
                self.status_changed.emit("Activo")
                self.fetch_quota()
        else:
            self.timer.stop()
            self.status_changed.emit("Desactivado")

    def stop_timer(self) -> None:
        """Stop all timers and gracefully terminate any running worker."""
        self.timer.stop()
        self._quota_backoff_timer.stop()
        self._wait_retry_timer.stop()
        self._rate_retry_timer.stop()
        if self.is_running and self.worker:
            self.worker.stop_gracefully()

    def shutdown(self) -> None:
        """Shut down the service, releasing all locks and terminating workers."""
        self.timer.stop()
        self._quota_backoff_timer.stop()
        self._wait_retry_timer.stop()
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
        self.is_running = False
        self.is_waiting = False
        self.current_cmd = []
        self.local_dir = None
        self._error_lines.clear()
        self._last_event_status = None
        self.status_changed.emit("Detenido")

    def on_lock_released(self, released_path: str) -> None:
        """Resume a waiting sync when a relevant path lock is released.

        Args:
            released_path: Absolute path that was unlocked.
        """
        conf = self._get_service_config()
        if not conf:
            return
        local_dir = conf.get("local_dir")
        if not local_dir or not self.is_waiting or self.is_running:
            return
        abs_local = os.path.abspath(local_dir)
        abs_released = os.path.abspath(released_path)
        if abs_released == abs_local or abs_local.startswith(abs_released + os.sep):
            self.log_message.emit(f"{self.service_name}: Ruta liberada, reanudando sincronización...")
            QTimer.singleShot(1000, self.sync)

    def sync(self, force_resync: bool = False) -> None:
        """Start a synchronization run for this service.

        Args:
            force_resync: If True, append --resync to the rclone command.
        """
        if self.is_running:
            self.log_message.emit(f"{self.service_name}: Ya hay una sincronización en curso.")
            return

        conf = self._get_service_config()
        if not conf:
            self.status_changed.emit("Desactivado")
            return

        if self._quota_backoff_active:
            self.log_message.emit(f"{self.service_name}: La API está limitada. Reintentando en unos minutos.")
            return

        self.cleanup_rclone_lock_files()
        self.local_dir = conf.get("local_dir")
        self.remote_dir = conf.get("remote_dir") or f"{self.service_name}:"

        provider_key = conf.get("provider")

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
            self._wait_retry_timer.start(5000)
            return

        self.is_waiting = False
        self._wait_retry_timer.stop()

        mode = self._get_mode()
        cmd = self._build_rclone_command(mode, self.local_dir, self.remote_dir, provider_key)
        exclusions_str = conf.get("exclusions", "")
        if exclusions_str:
            for pattern in exclusions_str.splitlines():
                if pattern.strip():
                    cmd.extend(["--exclude", pattern.strip()])

        cmd.extend(["--min-age", "30s", "--local-no-check-updated"])

        if mode == "bisync":
            if force_resync or self.force_resync_next:
                if "--resync" not in cmd:
                    cmd.append("--resync")
                self.force_resync_next = False
                self.log_message.emit(f"{self.service_name}: Re-sincronización forzada activada.")
        else:
            if force_resync or self.force_resync_next:
                self.force_resync_next = False
                self.log_message.emit(f"{self.service_name}: El modo {mode} no usa --resync; se reinicia la tarea.")

        self.start_process(cmd)

    def force_resync(self) -> None:
        """Trigger an immediate resync, or schedule one if a sync is in progress."""
        if self.is_running:
            self.force_resync_next = True
            self.log_message.emit(f"{self.service_name}: Re-sincronización programada al finalizar.")
            return
        if self._quota_backoff_active:
            self.log_message.emit(f"{self.service_name}: API limitada. Re-sincronización pendiente hasta nuevo intento.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def start_process(self, cmd_list: list[str]) -> None:
        """Launch a ProcessWorker to execute the given rclone command.

        Args:
            cmd_list: Full command-line arguments for rclone.
        """
        self.is_running = True
        self.current_cmd = cmd_list
        self.needs_resync = False
        self._error_lines = []
        self._last_event_status = None
        self.status_changed.emit("Sincronizando")
        self.log_message.emit(f"{self.service_name}: Iniciando sincronización...")

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

        self.worker = ProcessWorker(self.service_name, self.progress_key, cmd_list)
        self.worker.log_line.connect(self.handle_worker_line, Qt.ConnectionType.QueuedConnection)
        self.worker.update_ui.connect(self.handle_worker_event, Qt.ConnectionType.QueuedConnection)
        self.worker.finished.connect(self.process_finished, Qt.ConnectionType.QueuedConnection)
        self.worker.start()

    def handle_worker_line(self, _service_name: str, line: str) -> None:
        """Process a single line of output from the worker subprocess.

        Args:
            _service_name: Service name (unused, received from signal).
            line: Raw output line from rclone.
        """
        clean_line = self.clean_log(line)
        if not clean_line:
            return
        if STATS_NOISE_PATTERN.match(clean_line):
            return
        self._emit_stats_event(clean_line)
        self._handle_quota_line(clean_line)
        logging.info(f"[rclone:{self.service_name}] {clean_line}")
        normalized = clean_line.lower()
        if "error" in normalized or "failed" in normalized:
            self._error_lines.append(clean_line)
        if "ERROR" in clean_line or "Failed" in clean_line:
            self.log_message.emit(f"[{self.service_name} Error] {clean_line}")
        else:
            self.log_message.emit(f"[{self.service_name}] {clean_line}")
        self.check_resync_trigger(normalized)
        self.check_prompt(clean_line)
        self._check_credential_error(clean_line)

    def handle_worker_event(self, service: str, percent: int, event_type: str) -> None:
        """Forward a progress event from the worker to the UI.

        Args:
            service: Service key identifying the progress source.
            percent: Current completion percentage.
            event_type: Type of event (progress, error, start, etc.).
        """
        payload = {"percent": percent, "event": event_type}
        self.progress_updated.emit(service, payload)
        self._sync_status_from_event(event_type)

    def _sync_status_from_event(self, event_type: str) -> None:
        mapping = {
            "error": "Error",
            "warning": "Advertencia",
            "start": "Escaneando",
            "progress": "Sincronizando"
        }
        if event_type == "warning" and self._last_event_status in ("Sincronizando", "Escaneando"):
            return
        status = mapping.get(event_type, "Sincronizando")
        if status != self._last_event_status:
            self.status_changed.emit(status)
            self._last_event_status = status

    def check_resync_trigger(self, line: str) -> None:
        """Check if an output line indicates a --resync is required.

        Args:
            line: A cleaned line of rclone output.
        """
        triggers = ["Must run --resync", "bisync aborted", "run --resync", "critical error", "Safety abort"]
        if any(t.lower() in line.lower() for t in triggers):
            if not self.needs_resync:
                self.log_message.emit(f"{self.service_name}: Se requiere Re-sincronización (--resync).")
            self.needs_resync = True

    def check_prompt(self, line: str) -> None:
        """Auto-confirm interactive y/n prompts from rclone.

        Args:
            line: A cleaned line of rclone output.
        """
        lower = line.lower()
        if "[y/n]" in lower or "[y/N]" in line:
            self.log_message.emit(f"[{self.service_name}] Confirmando prompt: {line}")
            if self.worker:
                self.worker.send_input("y\n")

    def _emit_stats_event(self, line: str) -> None:
        """Classify a verbose log line and emit a stats event for the counters.

        Emite ``stats_event(service_key, category, detail)`` donde ``category``
        es ``"completed"`` (archivo transferido), ``"warnings"`` o ``"critical"``.

        Args:
            line: Cleaned line of rclone output.
        """
        match = TRANSFERRED_FILE_PATTERN.search(line)
        if match:
            filename = match.group(1).strip()
            self.stats_event.emit(self.progress_key, "completed", filename)
            return
        lower = line.lower()
        if any(hint in lower for hint in ERROR_HINTS):
            if "errors:" not in lower:
                self.stats_event.emit(self.progress_key, "critical", line)
        elif any(hint in lower for hint in WARNING_HINTS):
            self.stats_event.emit(self.progress_key, "warnings", line)

    def _parse_progress(self, text: str) -> dict | None:
        json_data = self._try_parse_json_progress(text)
        if json_data:
            return json_data
        match = PROGRESS_PATTERN.search(text)
        if not match:
            return None
        data = {}
        data["percent"] = int(match.group(1))
        speed = SPEED_PATTERN.search(text)
        if speed:
            data["speed"] = speed.group(1)
        eta = ETA_PATTERN.search(text)
        if eta:
            data["eta"] = eta.group(1)
        data["alert"] = bool(re.search(r"error|failed|panic", text, re.IGNORECASE))
        if data["alert"]:
            data["event"] = "error"
        return data

    def _try_parse_json_progress(self, text: str) -> dict | None:
        stripped = text.strip()
        if not stripped.startswith("{") or not stripped.endswith("}"):
            return None
        try:
            payload = json.loads(stripped)
        except ValueError:
            return None
        percent = payload.get("percent") or payload.get("progress") or payload.get("percentage")
        if percent is None:
            return None
        data = {}
        data["percent"] = int(float(percent))
        speed = payload.get("speed") or payload.get("bytesPerSecond")
        if speed:
            data["speed"] = str(speed)
        eta = payload.get("eta") or payload.get("timeRemain")
        if eta:
            data["eta"] = str(eta)
        level = payload.get("level", "").lower()
        data["alert"] = level == "error" or bool(payload.get("error")) or bool(payload.get("panic"))
        return data

    def _emit_progress(self, text: str) -> None:
        parsed = self._parse_progress(text)
        if parsed:
            self.progress_updated.emit(self.progress_key, parsed)

    def _get_mode(self) -> str:
        conf = self._get_service_config() or {}
        return conf.get("mode", "bisync")

    def _build_rclone_command(self, mode: str, src: str, dst: str, provider_key: str | None = None) -> list[str]:
        action = "bisync"
        extras = []
        if mode == "copy":
            action = "copy"
            extras = ["--create-empty-src-dirs"]
        elif mode == "sync":
            action = "sync"
            extras = []

        rclone_bin = get_rclone_binary()
        cmd = [
            rclone_bin, action, src, dst, "--verbose", "--checksum",
            "--stats", "5s", "--stats-one-line",
            "--filter-from", self.filter_file,
        ]
        if action != "bisync":
            cmd.append("--progress")
        if extras:
            cmd.extend(extras)
        return self._apply_cloud_flags(cmd, provider_key)

    def clean_log(self, text: str) -> str:
        """Strip ANSI escape codes from a log line.

        Args:
            text: Raw log line that may contain ANSI sequences.

        Returns:
            The cleaned text with ANSI codes removed.
        """
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text).strip()

    @staticmethod
    def verify_remote(remote_name: str) -> tuple[bool, str]:
        """Verify that an rclone remote is accessible and credentials are valid.

        Args:
            remote_name: Name of the rclone remote to verify.

        Returns:
            A tuple of (success, message) where success indicates validity.
        """
        try:
            rclone_bin = get_rclone_binary()
            result = subprocess.run(
                [rclone_bin, "lsd", f"{remote_name}:"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True, "Credenciales válidas"
            return False, result.stderr.strip() or result.stdout.strip() or f"Error código {result.returncode}"
        except FileNotFoundError:
            return False, "rclone no encontrado"
        except subprocess.TimeoutExpired:
            return False, "Tiempo de espera agotado"
        except Exception as e:
            return False, str(e)

    def _check_credential_error(self, line: str) -> None:
        lower = line.lower()
        if any(p in lower for p in CREDENTIAL_ERROR_PATTERNS):
            self.credential_error.emit(f"{self.service_name}: {line.strip()}")

    def process_finished(self, exit_code: int) -> None:
        """Handle completion of the rclone subprocess.

        Args:
            exit_code: The exit code returned by the process.
        """
        self.is_running = False
        timestamp = int(datetime.now().timestamp())

        if self.needs_resync:
            if "--resync" in self.current_cmd:
                logging.info(f"[{self.service_name}] Falló la recuperación (--resync). Código: {exit_code}")
                self.log_message.emit(f"{self.service_name}: Falló la recuperación (--resync). Se reintentará luego.")
                self.needs_resync = False
            else:
                logging.info(f"[{self.service_name}] Auto-recuperación (--resync) iniciada tras código {exit_code}")
                self.log_message.emit(f"{self.service_name}: Ejecutando auto-recuperación (--resync)...")
                cmd_copy = list(self.current_cmd)
                if "--resync" not in cmd_copy:
                    cmd_copy.append("--resync")
                self.start_process(cmd_copy)
                return

        if self.force_resync_next:
            self.force_resync_next = False
            if self.local_dir:
                self.coordinator.release_lock(self.local_dir)
            self.log_message.emit(f"{self.service_name}: Ejecutando re-sincronización programada...")
            self.sync(force_resync=True)
            return

        if self.local_dir:
            self.coordinator.release_lock(self.local_dir)

        lockfile_error = (
            exit_code == 1 and self._error_lines and any(
                "lockfile" in line.lower() for line in self._error_lines
            )
        )
        quota_error = self._quota_triggered and exit_code != 0
        resolved_exit_code = 0 if lockfile_error or quota_error else exit_code

        logging.info(f"[{self.service_name}] Sincronización finalizada. Código={exit_code} -> resuelto={resolved_exit_code} | lockfile_error={lockfile_error} | quota={self._quota_triggered} | errores_capturados={len(self._error_lines)}")

        if resolved_exit_code == 0:
            if self._quota_triggered:
                self.status_changed.emit("Limitado (API)")
            else:
                if self.rate_level > 0:
                    self.rate_level -= 1
                    self._persist_rate_level()
                    self.log_message.emit(
                        f"{self.service_name}: Sincronización exitosa. Ritmo recuperado "
                        f"(nivel {self.rate_level})."
                    )
                self.status_changed.emit("Activo")
            self.sync_finished.emit(timestamp)
            self.fetch_quota()
            if lockfile_error:
                self.log_message.emit(f"{self.service_name}: Error de lockfile ignorado. Se considera la tarea como exitosa.")
            elif self._quota_triggered:
                self.log_message.emit(f"{self.service_name}: Saturación de API detectada. Queda en estado limitado.")
            else:
                self.log_message.emit(f"{self.service_name}: Sincronización completada.")
        else:
            self.status_changed.emit("Error")
            self.log_message.emit(f"{self.service_name}: Error (Código {resolved_exit_code}). Verifique logs.")
            for err_line in self._error_lines:
                logging.error(f"[{self.service_name} error_line] {err_line}")

        self.worker = None
        self._error_lines.clear()
        self._last_event_status = None
