# © 2026 Miguel Fernando Cárdenas Alvear (FerDev).
# Todos los derechos reservados. Queda prohibida la reproducción, distribución o modificación de este software sin autorización expresa del autor.


import os
import sys
from PyQt6.QtCore import QObject

class AutostartManager(QObject):
    def __init__(self):
        super().__init__()
        self.autostart_dir = os.path.expanduser("~/.config/autostart")
        self.desktop_file = os.path.join(self.autostart_dir, "sync-master.desktop")

    def is_enabled(self):
        return os.path.exists(self.desktop_file)

    def set_enabled(self, enabled):
        if enabled:
            self.enable()
        else:
            self.disable()

    def enable(self):
        os.makedirs(self.autostart_dir, exist_ok=True)
        
        # Get current AppImage path or script path
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # This shouldn't happen with our manual AppImage but good for standard freezing
            app_path = sys.executable
        else:
            # For our AppImage, sys.argv[0] or the environment variable set by AppRun
            app_path = os.environ.get('APPIMAGE', sys.argv[0])
            if not os.path.isabs(app_path):
                app_path = os.path.abspath(app_path)

        content = f"""[Desktop Entry]
Type=Application
Name=Sync Master
Comment=Sincronizador de Nube (OneDrive y Google Drive)
Exec="{app_path}" --minimized
Icon=sync-master
StartupNotify=false
Terminal=false
Categories=Utility;
"""
        with open(self.desktop_file, "w") as f:
            f.write(content)

    def disable(self):
        if os.path.exists(self.desktop_file):
            os.remove(self.desktop_file)
