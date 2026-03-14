
import os
from PyQt6.QtCore import QObject, pyqtSignal

class SyncCoordinator(QObject):
    lock_released = pyqtSignal(str) # Emite la ruta absoluta liberada

    def __init__(self):
        super().__init__()
        self.active_paths = {} # path -> manager_name

    def is_path_busy(self, path):
        """ Verifica si la ruta o alguna de sus rutas madre/hija están ocupadas. """
        if not path: return False
        
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
        if self.is_path_busy(path):
            return False
        
        self.active_paths[os.path.abspath(path)] = manager_name
        return True

    def release_lock(self, path):
        abs_path = os.path.abspath(path)
        if abs_path in self.active_paths:
            del self.active_paths[abs_path]
            self.lock_released.emit(abs_path)
