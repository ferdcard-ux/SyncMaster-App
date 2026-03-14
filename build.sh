#!/bin/bash
export ARCH=x86_64

# Manual AppImage Construction (fallback when appimagetool fails in container)
if [ ! -f "runtime-x86_64" ]; then
    echo "Error: runtime-x86_64 not found. Please download it."
    exit 1
fi

echo "Bundling Python Runtime and Dependencies..."
# 1. Python Binary
mkdir -p AppDir/usr/bin
cp /usr/bin/python3 AppDir/usr/bin/

# 2. Python Standard Library
mkdir -p AppDir/usr/lib/python3.10
echo "Copying Standard Library..."
cp -r /usr/lib/python3.10/* AppDir/usr/lib/python3.10/

# 3. Site Packages (PyQt6 from local user install)
mkdir -p AppDir/usr/lib/python3.10/site-packages
echo "Copying PyQt6..."
# Copy PyQt6 and sip from local packages
# Assuming they are in ~/.local/lib/python3.10/site-packages
USER_SITE="/home/miguel-c/.local/lib/python3.10/site-packages"
if [ -d "$USER_SITE/PyQt6" ]; then
    cp -r "$USER_SITE/PyQt6" AppDir/usr/lib/python3.10/site-packages/
    # Also copy sip module if present (PyQt6 depends on it)
    # It might be separate or inside. Usually 'PyQt6_sip'.
    if [ -d "$USER_SITE/PyQt6_sip" ]; then
         cp -r "$USER_SITE/PyQt6_sip" AppDir/usr/lib/python3.10/site-packages/
    fi
else
    echo "Warning: PyQt6 not found in $USER_SITE"
fi

# 4. Shared Libs
# Copy libpython and Qt libs if needed
find /usr/lib -name "libpython3.10.so*" -exec cp {} AppDir/usr/lib/ \;
find /usr/lib/x86_64-linux-gnu -name "libpython3.10.so*" -exec cp {} AppDir/usr/lib/ \;

# --- BUNDLE PYQT6 INTERNAL LIBS ---
echo "Bundling PyQt6 internal Qt libraries..."
PYQT_LIB_DIR="AppDir/usr/lib/python3.10/site-packages/PyQt6/Qt6/lib"
if [ -d "$PYQT_LIB_DIR" ]; then
    cp -P "$PYQT_LIB_DIR"/*.so* AppDir/usr/lib/
fi

# --- BUNDLE PYQT6 PLUGINS ---
echo "Bundling PyQt6 plugins..."
PYQT_PLUGIN_DIR="AppDir/usr/lib/python3.10/site-packages/PyQt6/Qt6/plugins"
if [ -d "$PYQT_PLUGIN_DIR" ]; then
    mkdir -p AppDir/usr/plugins
    cp -r "$PYQT_PLUGIN_DIR"/* AppDir/usr/plugins/
fi


echo "Updating application source in AppDir..."
cp main.py AppDir/
cp version.py AppDir/
mkdir -p AppDir/managers AppDir/ui AppDir/assets
cp managers/*.py AppDir/managers/
cp ui/*.py AppDir/ui/
cp assets/* AppDir/assets/ 2>/dev/null || true

# Icons for AppImage integration
cp assets/logo.png AppDir/sync-master.png
cat > AppDir/sync-master.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Sync Master
Exec=python3 main.py %u
Icon=sync-master
Categories=Utility;
X-AppImage-Name=Sync Master
Terminal=false
EOF
chmod +x AppDir/sync-master.desktop

# 5. Bundling external binaries (rclone, onedrive)
mkdir -p AppDir/usr/bin
cp $(which rclone) AppDir/usr/bin/ 2>/dev/null || true
cp $(which onedrive) AppDir/usr/bin/ 2>/dev/null || true

echo "Creating SquashFS image..."
mksquashfs AppDir SyncMaster.squashfs -root-owned -noappend

echo "Concatenating runtime and image..."
cat runtime-x86_64 SyncMaster.squashfs > SyncMaster-x86_64.AppImage
chmod +x SyncMaster-x86_64.AppImage

echo "Done: SyncMaster-x86_64.AppImage created."
rm SyncMaster.squashfs
