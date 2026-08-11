# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


import os

from PyQt6.QtCore import QObject, pyqtSignal


class SyncCoordinator(QObject):
    lock_released = pyqtSignal(str) # Emite la ruta absoluta liberada

    def __init__(self):
        """Initialize the sync coordinator with an empty lock registry."""
        super().__init__()
        self.active_paths = {} # path -> manager_name

    def is_path_busy(self, path):
        """Check whether a path or any of its ancestors/descendants is locked.

        Args:
            path: The filesystem path to check.

        Returns:
            True if the path or a related path is currently locked.
        """
        if not path:
            return False

        path = os.path.abspath(path)

        for active_path in self.active_paths:
            # Caso 1: La misma ruta
            if path == active_path:
                return True
            # Caso 2: La ruta solicitada es subcarpeta de una activa (ej. /A/B ocupada, pido /A/B/C)
            if path.startswith(active_path + os.sep):
                return True
            # Caso 3: La ruta solicitada es padre de una activa (ej. /A/B/C ocupada, pido /A/B)
            if active_path.startswith(path + os.sep):
                return True

        return False

    def acquire_lock(self, path, manager_name):
        """Acquire an exclusive lock on a path for a given manager.

        Args:
            path: The filesystem path to lock.
            manager_name: Identifier of the manager requesting the lock.

        Returns:
            True if the lock was acquired, False if the path is already busy.
        """
        if self.is_path_busy(path):
            return False

        self.active_paths[os.path.abspath(path)] = manager_name
        return True

    def release_lock(self, path):
        """Release the lock on a path and notify waiting managers.

        Args:
            path: The filesystem path to unlock.
        """
        abs_path = os.path.abspath(path)
        if abs_path in self.active_paths:
            del self.active_paths[abs_path]
            self.lock_released.emit(abs_path)
