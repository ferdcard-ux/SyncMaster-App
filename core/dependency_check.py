import logging
import os
import shutil
import sys

from core.paths import get_app_data_dir, get_install_dir, get_rclone_binary


def find_rclone():
    binary = get_rclone_binary()
    search_paths = []

    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        search_paths.append(os.path.join(sys._MEIPASS, binary))

    base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    search_paths.append(os.path.join(base_dir, binary))

    search_paths.append(os.path.join(get_install_dir(), binary))

    search_paths.append(os.path.join(get_app_data_dir(), binary))

    for path in search_paths:
        if os.path.exists(path) and os.path.isfile(path):
            return os.path.abspath(path)

    # Fallback: search in system PATH
    which_path = shutil.which(binary)
    if which_path:
        return os.path.abspath(which_path)

    return None


def check_dependencies():
    missing = []

    rclone_path = find_rclone()
    if rclone_path:
        logging.info(f"rclone encontrado en: {rclone_path}")
    else:
        missing.append(
            "rclone — indispensable para todas las sincronizaciones.\n"
            "Instálalo desde https://rclone.org/downloads/ o asegúrate de que esté en el PATH del sistema."
        )

    return missing


def format_missing_deps(missing_deps):
    lines = []
    for dep in missing_deps:
        lines.append(dep)
    return "\n\n".join(lines)
