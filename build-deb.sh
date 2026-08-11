#!/bin/bash
set -euo pipefail

# ==========================================
#  SyncMaster .deb Package Builder
#  Produces: syncmaster_<version>_amd64.deb
# ==========================================

VERSION=$(grep "VERSION =" version.py | cut -d'"' -f2)
if [ -z "$VERSION" ]; then
    VERSION="1.9.0"
fi

PACKAGE="syncmaster"
ARCH="amd64"
DEB_NAME="${PACKAGE}_${VERSION}_${ARCH}"
BUILD_DIR="deb-build/${DEB_NAME}"

echo "=========================================="
echo "  Building ${DEB_NAME}.deb"
echo "=========================================="

# Clean previous build
rm -rf deb-build
mkdir -p "${BUILD_DIR}/DEBIAN"
chmod 0755 "${BUILD_DIR}/DEBIAN"
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/lib/${PACKAGE}"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${BUILD_DIR}/usr/share/doc/${PACKAGE}"

# ==========================================
# 1. Control file
# ==========================================
echo "[1/5] Creating DEBIAN/control..."
cat > "${BUILD_DIR}/DEBIAN/control" <<EOF
Package: ${PACKAGE}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10), python3-pyqt6
Recommends: rclone
Suggests: python3-pyqt6.qtsvg
Maintainer: Miguel Fernando Cardenas Alvear (FerDev) <ferdcard@proton.me>
Homepage: https://github.com/ferdcard-ux/SyncMasterPython
Description: Sincronizacion propietaria con monitoreo en tiempo real
 SyncMaster es una solucion propietaria de sincronizacion para Linux
 que usa rclone como motor unico para Google Drive, OneDrive, Mega
 y otros proveedores. Incluye monitoreo en tiempo real, auto-recuperacion,
 quota por servicio y modo offline.
EOF

# ==========================================
# 2. Application files
# ==========================================
echo "[2/5] Copying application files..."
APP_DIR="${BUILD_DIR}/usr/lib/${PACKAGE}"

# Core files
cp main.py "${APP_DIR}/"
cp version.py "${APP_DIR}/"

# Modules
mkdir -p "${APP_DIR}/managers" "${APP_DIR}/ui" "${APP_DIR}/core" "${APP_DIR}/assets"
cp managers/*.py "${APP_DIR}/managers/"
cp ui/*.py "${APP_DIR}/ui/"
cp core/*.py "${APP_DIR}/core/"
cp assets/* "${APP_DIR}/assets/" 2>/dev/null || true

# Config directory structure (will be created on first run)
# We create a symlink to the shared config location
mkdir -p "${BUILD_DIR}/etc/${PACKAGE}"
cat > "${BUILD_DIR}/etc/${PACKAGE}/default-config.json" <<'CONF'
{
    "onedrive": {"enabled": false, "local_dir": "", "remote_dir": "", "interval_minutes": 15, "exclusions": "", "mode": "bisync"},
    "gdrive": {"enabled": false, "local_dir": "", "remote_dir": "", "interval_minutes": 15, "exclusions": "", "auto_dedupe": true, "mode": "bisync"},
    "local_sync": {"enabled": false, "local_dir_a": "", "local_dir_b": "", "interval_minutes": 15, "exclusions": "", "mode": "bisync"},
    "general": {"autostart": false, "welcome_shown": false},
    "rclone_services": [],
    "local_services": []
}
CONF

# ==========================================
# 3. Launcher script
# ==========================================
echo "[3/5] Creating launcher..."
cat > "${BUILD_DIR}/usr/bin/syncmaster" <<'LAUNCHER'
#!/bin/bash
APP_DIR="/usr/lib/syncmaster"
cd "$APP_DIR" || exit 1
exec python3 main.py "$@"
LAUNCHER
chmod 755 "${BUILD_DIR}/usr/bin/syncmaster"

# ==========================================
# 4. Desktop integration
# ==========================================
echo "[4/5] Adding desktop integration..."
cp assets/logo.png "${BUILD_DIR}/usr/share/icons/hicolor/256x256/apps/syncmaster.png"

cat > "${BUILD_DIR}/usr/share/applications/syncmaster.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SyncMaster v$VERSION Private
Exec=/usr/bin/syncmaster %u
Icon=syncmaster
Categories=Utility;
Terminal=false
Comment=Sincronización propietaria con monitoreo en tiempo real
EOF

# ==========================================
# 5. Documentation
# ==========================================
echo "[5/5] Adding documentation..."
cp README.md "${BUILD_DIR}/usr/share/doc/${PACKAGE}/README.md"
cp docs/CHANGELOG.md "${BUILD_DIR}/usr/share/doc/${PACKAGE}/changelog"
cp docs/COPYRIGHT.txt "${BUILD_DIR}/usr/share/doc/${PACKAGE}/copyright"
gzip -9 -n "${BUILD_DIR}/usr/share/doc/${PACKAGE}/changelog" -c > "${BUILD_DIR}/usr/share/doc/${PACKAGE}/changelog.gz"
rm "${BUILD_DIR}/usr/share/doc/${PACKAGE}/changelog"

# ==========================================
# 6. Postinst script (auto-install rclone)
# ==========================================
echo "[6/6] Creating postinst script..."
cat > "${BUILD_DIR}/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e

MIN_VERSION="1.65"
RCLONE_INSTALLED=false

# Check if rclone is installed and meets minimum version
if command -v rclone >/dev/null 2>&1; then
    CURRENT=$(rclone version 2>/dev/null | head -1 | grep -oP '[\d]+\.[\d]+' | head -1)
    if [ -n "$CURRENT" ]; then
        MAJOR=$(echo "$CURRENT" | cut -d. -f1)
        MINOR=$(echo "$CURRENT" | cut -d. -f2)
        REQ_MAJOR=$(echo "$MIN_VERSION" | cut -d. -f1)
        REQ_MINOR=$(echo "$MIN_VERSION" | cut -d. -f2)
        if [ "$MAJOR" -gt "$REQ_MAJOR" ] || { [ "$MAJOR" -eq "$REQ_MAJOR" ] && [ "$MINOR" -ge "$REQ_MINOR" ]; }; then
            RCLONE_INSTALLED=true
            echo "rclone $CURRENT detectado (>= $MIN_VERSION requerido). OK."
        else
            echo "rclone $CURRENT detectado pero se requiere >= $MIN_VERSION. Actualizando..."
        fi
    fi
fi

if [ "$RCLONE_INSTALLED" = false ]; then
    echo "Instalando rclone (requerido para SyncMaster)..."
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL https://rclone.org/install.sh | bash || {
            echo ""
            echo "AVISO: No se pudo instalar rclone automaticamente."
            echo "Instalalo manualmente desde: https://rclone.org/downloads/"
            echo "SyncMaster no funcionara sin rclone."
        }
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://rclone.org/install.sh | bash || {
            echo ""
            echo "AVISO: No se pudo instalar rclone automaticamente."
            echo "Instalalo manualmente desde: https://rclone.org/downloads/"
            echo "SyncMaster no funcionara sin rclone."
        }
    else
        echo ""
        echo "AVISO: Ni curl ni wget disponibles. No se pudo instalar rclone."
        echo "Instalalo manualmente desde: https://rclone.org/downloads/"
        echo "SyncMaster no funcionara sin rclone."
    fi
fi

#DEBHELPER#

exit 0
POSTINST
chmod 0755 "${BUILD_DIR}/DEBIAN/postinst"

# ==========================================
# Build .deb
# ==========================================
echo ""
echo "Building .deb package..."

# Fix all permissions before packaging
find "${BUILD_DIR}" -type d -exec chmod 0755 {} \;
find "${BUILD_DIR}" -type f -exec chmod 0644 {} \;
chmod 0755 "${BUILD_DIR}/usr/bin/syncmaster"
chmod 0755 "${BUILD_DIR}/DEBIAN"
chmod 0755 "${BUILD_DIR}/DEBIAN/postinst" 2>/dev/null || true

dpkg-deb --root-owner-group --build "${BUILD_DIR}"

DEB_FILE="deb-build/${DEB_NAME}.deb"
if [ -f "$DEB_FILE" ]; then
    echo ""
    echo "=========================================="
    echo "  DONE: ${DEB_NAME}.deb"
    echo "  Size: $(du -h "$DEB_FILE" | cut -f1)"
    echo ""
    echo "  Install with:"
    echo "    sudo dpkg -i ${DEB_FILE}"
    echo "    sudo apt-get install -f  # fix deps"
    echo "=========================================="
else
    echo "ERROR: .deb build failed"
    exit 1
fi
