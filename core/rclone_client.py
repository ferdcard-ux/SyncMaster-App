# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.
from __future__ import annotations

import subprocess
import time

from core.paths import get_rclone_binary

# Tiempo de espera máximo para operaciones de configuración de rclone.
CONFIG_TIMEOUT_SECONDS = 60

# Proveedores que aceptan client_id/client_secret propios y su nombre de backend.
CLIENT_ID_PROVIDERS = {
    "drive": ("Google Drive", "client_id", "client_secret"),
    "onedrive": ("OneDrive", "client_id", "client_secret"),
}


def list_remotes() -> list[str]:
    """Return the list of configured rclone remote names.

    Returns:
        List of remote names without the trailing colon, or [] on failure.
    """
    try:
        result = subprocess.run(
            [get_rclone_binary(), "listremotes"],
            capture_output=True, text=True, timeout=CONFIG_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return []
        names = []
        for line in result.stdout.splitlines():
            name = line.strip().rstrip(":")
            if name:
                names.append(name)
        return names
    except Exception:
        return []


def remote_backend(remote: str) -> str | None:
    """Return the backend type of a configured remote, or None.

    Args:
        remote: Name of the rclone remote.

    Returns:
        Backend string such as 'drive', or None if unknown/failed.
    """
    try:
        result = subprocess.run(
            [get_rclone_binary(), "config", "show", remote],
            capture_output=True, text=True, timeout=CONFIG_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("type"):
                value = stripped.split("=", 1)[1].strip()
                return value or None
        return None
    except Exception:
        return None


def apply_client_id(remote: str, client_id: str, client_secret: str) -> tuple[bool, str]:
    """Write a custom client_id/client_secret into an existing remote.

    Args:
        remote: Name of the rclone remote to update.
        client_id: The user's own OAuth client ID.
        client_secret: The user's own OAuth client secret (may be empty).

    Returns:
        A tuple of (success, message).
    """
    if not remote:
        return False, "Debes indicar el nombre del remoto."
    if not client_id:
        return False, "Debes ingresar un Client ID."

    cmd = [get_rclone_binary(), "config", "update", remote]
    if client_id:
        cmd.append(f"client_id={client_id}")
    if client_secret:
        cmd.append(f"client_secret={client_secret}")
    cmd.append("--all")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=CONFIG_TIMEOUT_SECONDS,
        )
        if result.returncode == 0:
            return True, f"Client ID aplicado al remoto '{remote}'."
        message = result.stderr.strip() or result.stdout.strip() or f"Error código {result.returncode}"
        return False, message
    except subprocess.TimeoutExpired:
        return False, "Tiempo de espera agotado al aplicar el Client ID."
    except FileNotFoundError:
        return False, "rclone no encontrado."
    except Exception as e:  # pragma: no cover - defensivo
        return False, str(e)


def reconnect_command(remote: str) -> list[str]:
    """Build the rclone command to re-authorize an existing remote.

    Args:
        remote: Name of the rclone remote to reconnect.

    Returns:
        The argument list for ``rclone config reconnect <remote>``.
    """
    return [get_rclone_binary(), "config", "reconnect", remote]


def get_remote_dir_label(remote: str) -> str:
    """Return a friendly label for a remote, e.g. 'drive' -> 'Google Drive'."""
    provider = remote_backend(remote)
    if provider in CLIENT_ID_PROVIDERS:
        return CLIENT_ID_PROVIDERS[provider][0]
    return remote or ""


def supports_custom_client_id(remote: str) -> tuple[bool, str]:
    """Check whether a remote's backend accepts a custom client_id.

    Args:
        remote: Name of the rclone remote.

    Returns:
        A tuple of (supported, explanation).
    """
    provider = remote_backend(remote)
    if provider in CLIENT_ID_PROVIDERS:
        return True, CLIENT_ID_PROVIDERS[provider][0]
    return False, (f"El backend '{provider or 'desconocido'}' no admite un Client ID propio.")


def wait_ready(retries: int = 30, delay: float = 0.2) -> bool:
    """Wait until `rclone` responds, useful after editing the config file.

    Args:
        retries: Number of retry attempts.
        delay: Seconds between attempts.

    Returns:
        True if rclone answered within the given time.
    """
    for _ in range(retries):
        try:
            result = subprocess.run(
                [get_rclone_binary(), "config", "dump"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False
