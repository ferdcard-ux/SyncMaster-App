#!/bin/bash

APPIMAGE_PATH="$(readlink -f "$1")"
if [ -z "$1" ]; then
    echo "Uso: ./install_autostart.sh /ruta/a/SyncMaster-x86_64.AppImage"
    exit 1
fi

AUTOSTART_DIR="$HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"

cat > "$AUTOSTART_DIR/sync-master.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Sync Master
Comment=Sincronizador de Nube (OneDrive y Google Drive)
Exec="$APPIMAGE_PATH" --minimized
Icon=sync-master
StartupNotify=false
Terminal=false
Categories=Utility;
EOF

echo "Autostart configurado en: $AUTOSTART_DIR/sync-master.desktop"
echo "La aplicación se iniciará minimizada en el próximo arranque."
