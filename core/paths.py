from __future__ import annotations

import os
import sys


def is_windows() -> bool:
    return sys.platform == "win32"


def is_linux() -> bool:
    return sys.platform == "linux"


def get_app_data_dir() -> str:
    if is_windows():
        base = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        return os.path.join(base, "SyncMaster")
    return os.path.expanduser("~/.config/syncmaster")


def get_cache_dir() -> str:
    if is_windows():
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return os.path.join(base, "SyncMaster", "cache")
    return os.path.expanduser("~/.cache/syncmaster")


def get_logs_dir() -> str:
    return os.path.join(get_app_data_dir(), "logs")


def get_rclone_bisync_cache_dir() -> str:
    if is_windows():
        return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local")), "rclone", "bisync")
    return os.path.expanduser("~/.cache/rclone/bisync")


def get_config_file_path() -> str:
    return os.path.join(get_app_data_dir(), "config.json")


def get_rclone_filters_path() -> str:
    return os.path.join(get_app_data_dir(), "rclone_filters.txt")


def get_rclone_binary() -> str:
    if is_windows():
        return "rclone.exe"
    return "rclone"


def get_autostart_dir() -> str:
    if is_windows():
        return os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup")
    return os.path.expanduser("~/.config/autostart")


def get_install_dir() -> str:
    if is_windows():
        return os.environ.get("ProgramFiles", "C:\\Program Files") + "\\SyncMaster"
    return "/opt/syncmaster"


def get_mount_base_dir() -> str:
    if is_windows():
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return os.path.join(base, "SyncMaster", "Mounts")
    return os.path.expanduser("~/SyncMaster-Mounts")


def get_mount_dir(service_name: str) -> str:
    path = os.path.join(get_mount_base_dir(), service_name)
    try:
        os.makedirs(path, exist_ok=True)
    except PermissionError:
        import subprocess
        subprocess.run(
            ["pkexec", "mkdir", "-p", path],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    return path
