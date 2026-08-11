# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.

"""Catálogo de exclusiones por defecto según el proveedor de nube.

Cada preset se aplica al crear un servicio nuevo en la app y al migrar
servicios existentes que aún no tengan exclusiones configuradas.

Los patrones siguen la sintaxis nativa de rclone (un patrón por línea).
"""

from __future__ import annotations

# Base común para todos los servicios (código, entornos virtuales, temporales).
_BASE = (
    "**/.venv/**\n"
    "**/venv/**\n"
    "**/__pycache__/**\n"
    "*.pyc\n"
    "*.pyo\n"
    "**/node_modules/**\n"
    "**/target/**\n"
    "**/build/**\n"
    "**/dist/**\n"
    "**/.git/**\n"
    "**/.idea/**\n"
    "**/.vscode/**\n"
    "**/.vs/**\n"
    "**/obj/**\n"
    "**/debug/**\n"
    "**/release/**\n"
    "**/.cache/**\n"
    "**/*.tmp\n"
    "**/*.bak\n"
    "*~\n"
    "*.swp\n"
    "*.swo\n"
)

# Proveedores específicos.
_GOOGLE_DRIVE = _BASE + (
    ".Trash-**\n"
    "**/Thumbs.db\n"
    "**/.DS_Store\n"
    "desktop.ini\n"
    "~$*\n"
    "*.key\n"
    "*.pem\n"
    "*.log\n"
)

_ONEDRIVE = _BASE + (
    "**/Thumbs.db\n"
    "**/.DS_Store\n"
    "desktop.ini\n"
    "~$*\n"
    "*.key\n"
    "*.pem\n"
    "*.log\n"
)

_MEGA = _BASE + (
    "**/Thumbs.db\n"
    "**/.DS_Store\n"
    "~$*\n"
    "*.log\n"
)

_DROPBOX = _BASE + (
    "**/.dropbox.cache/**\n"
    "**/Thumbs.db\n"
    "**/.DS_Store\n"
    "~$*\n"
)

_GENERIC = _BASE + (
    "**/Thumbs.db\n"
    "**/.DS_Store\n"
    "*.log\n"
)

DEFAULT_EXCLUSIONS: dict[str, str] = {
    "drive": _GOOGLE_DRIVE,
    "google": _GOOGLE_DRIVE,
    "google drive": _GOOGLE_DRIVE,
    "gdrive": _GOOGLE_DRIVE,
    "onedrive": _ONEDRIVE,
    "one drive": _ONEDRIVE,
    "mega": _MEGA,
    "dropbox": _DROPBOX,
    "s3": _GENERIC,
    "swift": _GENERIC,
    "b2": _GENERIC,
    "box": _GENERIC,
    "pcloud": _GENERIC,
    "yandex": _GENERIC,
    "nextcloud": _GENERIC,
    "webdav": _GENERIC,
    "sftp": _GENERIC,
    "ftp": _GENERIC,
    "smb": _GENERIC,
    "local": _GENERIC,
    "generic": _GENERIC,
}

# Clave usada cuando el proveedor no está en el catálogo.
GENERIC_KEY = "generic"


def get_default_exclusions(provider: str | None) -> str:
    """Return the default exclusions preset for a cloud provider.

    Args:
        provider: Backend/provider name (e.g. 'drive', 'onedrive', 'mega').

    Returns:
        Multi-line exclusion string suitable for rclone ``--exclude``.
    """
    key = (provider or "").strip().lower()
    preset = DEFAULT_EXCLUSIONS.get(key) or DEFAULT_EXCLUSIONS.get(GENERIC_KEY)
    if preset is None:
        preset = _GENERIC
    return preset
