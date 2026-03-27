# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

# Sync Master Rclone service manager.
# Copyright 2026 FerDev

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread
import json
import os
import re
import subprocess
from datetime import datetime
import logging
import traceback

PROGRESS_PATTERN = re.compile(r"(\d+)\s*%", re.IGNORECASE)
SPEED_PATTERN = re.compile(r"(\d+(?:\.\d+)?\s*[KMGT]?i?B/s)", re.IGNORECASE)
ETA_PATTERN = re.compile(r"ETA\s*([^,\s]+)", re.IGNORECASE)


class ProcessWorker(QThread):
    log_line = pyqtSignal(str, str)
    update_ui = pyqtSignal(str, int, str)
    finished = pyqtSignal(int)

    PROGRESS_REGEX = re.compile(r"(\d+)\s*%", re.IGNORECASE)
    START_KEYWORDS = ["scanning", "init", "starting", "preparing", "queueing"]

    def __init__(self, service_name, widget_key, cmd_list):
        super().__init__()
        self.service_name = service_name
        self.widget_key = widget_key
        self.cmd_list = list(cmd_list)
        self._stop_requested = False
        self._process = None

    def run(self):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        try:
            self._process = subprocess.Popen(
                self.cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                env=env
            )
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
                    # Ignorar líneas con codificación inválida (evita crash del thread)
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
                
                # Auto-confirmación de prompts si rclone se queda esperando
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

    def send_input(self, payload):
        if self._process and self._process.stdin:
            try:
                self._process.stdin.write(payload)
                self._process.stdin.flush()
            except Exception:
                pass

    def stop(self):
        self._stop_requested = True
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def _emit_status(self, line):
        percent = self._extract_percent(line)
        event_type = self._determine_event_type(line)
        if percent is not None:
            print(f"DEBUG: Detectado {percent}% para {self.service_name}")
            self.update_ui.emit(self.widget_key, percent, event_type)
        elif event_type != "progress":
            self.update_ui.emit(self.widget_key, 0, event_type)

    def _extract_percent(self, line):
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

    def _determine_event_type(self, line):
        lower = line.lower()
        if "error" in lower or "failed" in lower:
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

    CLOUD_CONCURRENCY_FLAGS = ["--transfers", "2", "--checkers", "4", "--tpslimit", "5"]
    DRIVE_CHUNK_FLAG = ["--drive-chunk-size", "64M"]
    CLOUD_KEYWORDS = ["drive", "mega", "onedrive", "cloud", "s3", "ws", "ftp", "dropbox"]

    def __init__(self, config_manager, coordinator, service_name):
        super().__init__()
        self.config_manager = config_manager
        self.coordinator = coordinator
        self.service_name = service_name
        self.timer = QTimer()
        self.timer.timeout.connect(self.sync)
        self.coordinator.lock_released.connect(self.on_lock_released)
        self.worker = None
        self._last_event_status = None
        self.progress_key = f"rclone:{self.service_name}"
        self.is_running = False
        self.is_waiting = False
        self.local_dir = None
        self.remote_dir = None
        self.needs_resync = False
        self.force_resync_next = False
        self.current_cmd = []
        self._error_lines = []
        self._quota_backoff_active = False
        self._quota_triggered = False
        self._quota_backoff_timer = QTimer(self)
        self._quota_backoff_timer.setSingleShot(True)
        self._quota_backoff_timer.timeout.connect(self._release_quota_backoff)

        # Filtros globales para portabilidad y evitar errores de symlinks
        self.filter_file = os.path.join(os.path.expanduser("~"), ".config", "syncmaster", "rclone_filters.txt")
        self._ensure_global_filters()

    def _get_service_config(self):
        services = self.config_manager.get("rclone_services", []) or []
        for service in services:
            if service.get("name") == self.service_name:
                return service
        return None

    def _is_cloud_provider(self, provider_key):
        candidate = (provider_key or self.service_name or "").lower()
        return any(keyword in candidate for keyword in self.CLOUD_KEYWORDS)

    def _apply_cloud_flags(self, cmd, provider_key):
        if not self._is_cloud_provider(provider_key):
            return cmd
        candidate = (provider_key or self.service_name or "").lower()
        cmd.extend(self.CLOUD_CONCURRENCY_FLAGS)
        if "drive" in candidate:
            cmd.extend(self.DRIVE_CHUNK_FLAG)
        return cmd

    def _activate_quota_backoff(self):
        if self._quota_backoff_active:
            return
        self._quota_backoff_active = True
        self._quota_triggered = True
        self.timer.stop()
        self.status_changed.emit("Limitado (API)")
        self.log_message.emit(f"[{self.service_name}] API Saturada. Entrando en modo de espera preventivo...")
        self._quota_backoff_timer.start(5 * 60 * 1000)

    def _release_quota_backoff(self):
        self._quota_backoff_active = False
        self._quota_triggered = False
        self.log_message.emit(f"{self.service_name}: Modo limitado terminado. Reanudando la programación automática.")
        conf = self._get_service_config()
        if conf and conf.get("enabled", True):
            self.status_changed.emit("Activo")
            self.start_timer()

    def _handle_quota_line(self, text):
        if "quota exceeded" in text.lower():
            self._activate_quota_backoff()

    def _ensure_global_filters(self):
        """Garantiza la existencia del archivo de filtros global con reglas por defecto."""
        try:
            os.makedirs(os.path.dirname(self.filter_file), exist_ok=True)
            if not os.path.exists(self.filter_file):
                default_content = (
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
                )
                with open(self.filter_file, "w", encoding="utf-8") as f:
                    f.write(default_content)
        except Exception as e:
            print(f"Error al crear filtros globales: {e}")

    def start_timer(self):
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
        else:
            self.timer.stop()
            self.status_changed.emit("Desactivado")

    def stop_timer(self):
        self.timer.stop()
        if self.is_running and self.worker:
            self.worker.stop()
            self.worker.wait()
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

        if self._quota_backoff_active:
            self.log_message.emit(f"{self.service_name}: La API está limitada. Reintentando en unos minutos.")
            return

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
            return

        self.is_waiting = False

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

    def force_resync(self):
        if self.is_running:
            self.force_resync_next = True
            self.log_message.emit(f"{self.service_name}: Re-sincronización programada al finalizar.")
            return
        if self._quota_backoff_active:
            self.log_message.emit(f"{self.service_name}: API limitada. Re-sincronización pendiente hasta nuevo intento.")
            return
        self.force_resync_next = False
        self.sync(force_resync=True)

    def start_process(self, cmd_list):
        self.is_running = True
        self.current_cmd = cmd_list
        self.needs_resync = False
        self.status_changed.emit("Sincronizando")
        self.log_message.emit(f"{self.service_name}: Iniciando sincronización...")
        self._error_lines = []
        self._last_event_status = None

        if self.worker:
            self.worker.stop()
            self.worker.wait()

        self.worker = ProcessWorker(self.service_name, self.progress_key, cmd_list)
        self.worker.log_line.connect(self.handle_worker_line)
        self.worker.update_ui.connect(self.handle_worker_event)
        self.worker.finished.connect(self.process_finished)
        self.worker.finished.connect(self.worker.deleteLater) # Asegurar limpieza de recursos C++
        self.worker.start()

    def handle_worker_line(self, _service_name, line):
        # _service_name viene del worker pero usamos self.service_name para consistencia
        clean_line = self.clean_log(line)
        if not clean_line:
            return
        self._handle_quota_line(clean_line)
        normalized = clean_line.lower()
        if "error" in normalized or "failed" in normalized:
            self._error_lines.append(clean_line)
        if "ERROR" in clean_line or "Failed" in clean_line:
            self.log_message.emit(f"[{self.service_name} Error] {clean_line}")
        else:
            self.log_message.emit(f"[{self.service_name}] {clean_line}")
        self.check_resync_trigger(normalized)
        self.check_prompt(clean_line)

    def handle_worker_event(self, service, percent, event_type):
        payload = {"percent": percent, "event": event_type}
        self.progress_updated.emit(service, payload)
        self._sync_status_from_event(event_type)

    def _sync_status_from_event(self, event_type):
        mapping = {
            "error": "Error",
            "warning": "Advertencia",
            "start": "Escaneando",
            "progress": "Sincronizando"
        }
        status = mapping.get(event_type, "Sincronizando")
        if status != self._last_event_status:
            self.status_changed.emit(status)
            self._last_event_status = status

    def check_resync_trigger(self, line):
        triggers = ["Must run --resync", "bisync aborted", "run --resync", "critical error", "Safety abort"]
        if any(t.lower() in line.lower() for t in triggers):
            if not self.needs_resync:
                self.log_message.emit(f"{self.service_name}: Se requiere Re-sincronización (--resync).")
            self.needs_resync = True

    def check_prompt(self, line):
        lower = line.lower()
        if "[y/n]" in lower or "[y/N]" in line:
            self.log_message.emit(f"[{self.service_name}] Confirmando prompt: {line}")
            if self.worker:
                self.worker.send_input("y\n")

    def _parse_progress(self, text):
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

    def _try_parse_json_progress(self, text):
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

    def _emit_progress(self, text):
        parsed = self._parse_progress(text)
        if parsed:
            self.progress_updated.emit(self.progress_key, parsed)

    def _get_mode(self):
        conf = self._get_service_config() or {}
        return conf.get("mode", "bisync")

    def _build_rclone_command(self, mode, src, dst, provider_key=None):
        action = "bisync"
        extras = []
        if mode == "copy":
            action = "copy"
            extras = ["--create-empty-src-dirs"]
        elif mode == "sync":
            action = "sync"
            extras = []

        cmd = [
            "rclone", action, src, dst, "--verbose", "--checksum", "--progress",
            "--stats", "1s", "--stats-one-line",
            "--filter-from", self.filter_file,
            "--skip-links"
        ]
        if extras:
            cmd.extend(extras)
        return self._apply_cloud_flags(cmd, provider_key)

    def clean_log(self, text):
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text).strip()

    def process_finished(self, exit_code):
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

        lockfile_error = (
            exit_code == 1 and self._error_lines and any(
                "lockfile" in line.lower() for line in self._error_lines
            )
        )
        quota_error = self._quota_triggered and exit_code != 0
        resolved_exit_code = 0 if lockfile_error or quota_error else exit_code

        if resolved_exit_code == 0:
            if self._quota_triggered:
                self.status_changed.emit("Limitado (API)")
            else:
                self.status_changed.emit("Activo")
            self.sync_finished.emit(timestamp)
            if lockfile_error:
                self.log_message.emit(f"{self.service_name}: Error de lockfile ignorado. Se considera la tarea como exitosa.")
            elif self._quota_triggered:
                self.log_message.emit(f"{self.service_name}: Saturación de API detectada. Queda en estado limitado.")
            else:
                self.log_message.emit(f"{self.service_name}: Sincronización completada.")
        else:
            self.status_changed.emit("Error")
            self.log_message.emit(f"{self.service_name}: Error (Código {resolved_exit_code}). Verifique logs.")

        self.worker = None
        self._error_lines.clear()
        self._last_event_status = None
