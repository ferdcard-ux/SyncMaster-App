import os

from core.paths import get_app_data_dir, get_rclone_binary


def ensure_app_dirs():
    from core.paths import get_cache_dir, get_logs_dir
    for d in [get_app_data_dir(), get_logs_dir(), get_cache_dir()]:
        os.makedirs(d, exist_ok=True)


def find_rclone_binary():
    from core.dependency_check import find_rclone
    path = find_rclone()
    return path if path else get_rclone_binary()
