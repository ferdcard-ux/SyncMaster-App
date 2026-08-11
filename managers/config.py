# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


import json
import os

from core.exclusion_presets import get_default_exclusions
from core.paths import get_config_file_path


class ConfigManager:
    def __init__(self):
        """Initialize ConfigManager and load the configuration file."""
        self.config_file = get_config_file_path()
        self.config = {}
        self.load_config()

    def load_config(self):
        """Load configuration from disk, merging with built-in defaults."""
        defaults = {
            "onedrive": {
                "enabled": False,
                "local_dir": "",
                "remote_dir": "",
                "interval_minutes": 15,
                "exclusions": "",
                "mode": "bisync"
            },
            "gdrive": {
                "enabled": False,
                "local_dir": "",
                "remote_dir": "",
                "interval_minutes": 15,
                "exclusions": "",
                "auto_dedupe": True,
                "mode": "bisync"
            },
            "local_sync": {
                "enabled": False,
                "local_dir_a": "",
                "local_dir_b": "",
                "interval_minutes": 15,
                "exclusions": "",
                "mode": "bisync"
            },
            "general": {
                "autostart": False,
                "welcome_shown": False
            },
            "rclone_services": [],
            "local_services": []
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file) as f:
                    self.config = json.load(f)
                self._merge_defaults(self.config, defaults)
                self._migrate_exclusion_presets()
            except Exception as e:
                print(f"Error loading config: {e}")
                self.config = defaults
        else:
            self.config = defaults

    def _migrate_exclusion_presets(self):
        """Fill empty exclusions on existing services with the provider preset."""
        for service in self.config.get("rclone_services", []) or []:
            if not (service.get("exclusions") or "").strip():
                service["exclusions"] = get_default_exclusions(service.get("provider", ""))
        for key in ("gdrive", "onedrive"):
            conf = self.config.get(key)
            if isinstance(conf, dict) and not (conf.get("exclusions") or "").strip():
                conf["exclusions"] = get_default_exclusions("drive" if key == "gdrive" else "onedrive")
        for service in self.config.get("local_services", []) or []:
            if not (service.get("exclusions") or "").strip():
                service["exclusions"] = get_default_exclusions("local")

    def _merge_defaults(self, target, defaults):
        for key, value in defaults.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target.get(key), dict):
                self._merge_defaults(target[key], value)

    def save_config(self):
        """Persist the current configuration to disk as JSON."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        """Retrieve a configuration value by key.

        Args:
            key: The configuration key to look up.
            default: Value returned if the key does not exist.

        Returns:
            The configuration value or the provided default.
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """Set a configuration value and persist it to disk.

        Args:
            key: The configuration key to set.
            value: The value to assign.
        """
        self.config[key] = value
        self.save_config()
