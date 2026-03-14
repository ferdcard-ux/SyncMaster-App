
import json
import os

class ConfigManager:
    def __init__(self):
        self.config_file = os.path.expanduser("~/.config/sync_master/config.json")
        self.config = {}
        self.load_config()

    def load_config(self):
        defaults = {
            "onedrive": {
                "enabled": False,
                "local_dir": "",
                "remote_dir": "",
                "interval_minutes": 15,
                "exclusions": ""
            },
            "gdrive": {
                "enabled": False,
                "local_dir": "",
                "remote_dir": "",
                "interval_minutes": 15,
                "exclusions": "",
                "auto_dedupe": True
            },
            "local_sync": {
                "enabled": False,
                "local_dir_a": "",
                "local_dir_b": "",
                "interval_minutes": 15,
                "exclusions": ""
            },
            "general": {
                "autostart": False,
                "welcome_shown": False
            },
            "rclone_services": []
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                self._merge_defaults(self.config, defaults)
            except Exception as e:
                print(f"Error loading config: {e}")
                self.config = defaults
        else:
            self.config = defaults

    def _merge_defaults(self, target, defaults):
        for key, value in defaults.items():
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target.get(key), dict):
                self._merge_defaults(target[key], value)

    def save_config(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save_config()
