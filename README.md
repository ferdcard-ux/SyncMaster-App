# SyncMaster v1.9.0 — Linux (Bunker)

**SyncMaster v1.9.0** es la versión Linux de la solución propietaria de sincronización. Usa `rclone` como motor único para todos los proveedores de nube (Google Drive, OneDrive, Mega, Dropbox, etc.) con monitoreo en tiempo real, auto-recuperación, control de estados protegidos, seguimiento visual de progreso, información de quota por servicio y montaje remoto.

## Novedades en v1.9.0

### Montaje remoto y control directo
- **Montaje remoto**: botones "Montar"/"Desmontar" en cada tarjeta de servicio cloud para exponer el remote como punto de montaje FUSE.
- **Anillo de progreso clicable**: clic para pausar/reanudar la sincronización automática de cada servicio (con hover que muestra la acción).
- **Estados de montaje** sincronizados con la señal `mount_changed` de cada gestor.
- **Desmontaje automático** de los puntos de montaje al cerrar la aplicación.

### Pulido del monitoreo y resiliencia
- **Contadores precisos de estadísticas**: "Archivos Completados" cuenta archivos reales transferidos (Copied/Updated/Moved/Renamed, excluye borrados a papelera) desde el log de rclone, desacoplado del porcentaje del anillo.
- **Desglose por contador**: al pulsar cada contador se abre un diálogo filtrado por categoría — Completados con la lista de nombres de archivo, Advertencias y Errores con sus líneas originales, agrupados por servicio.
- **Estados en lenguaje cotidiano**: tooltips de las tarjetas explican cada estado sin tecnicismos.
- **Tooltips** en todos los controles activos (Montar/Desmontar, Pausar/Reanudar, anillo, navegación).
- **Tarjetas autocentradas**: con pocos servicios el bloque se centra en lugar de quedar pegado a la izquierda.
- **Exclusiones por proveedor**: presets por defecto y adicionales para Drive, OneDrive y Local.
- **Auto-ajuste de ritmo de transferencia**: ante límites de API (Quota exceeded, 429, rate limit) el servicio baja su concurrencia progresivamente y persiste el nivel.
- **Asistente de Client ID propio**: usa tu propio Client ID/Secret en Google Drive y OneDrive con reconexión automática vía `rclone config reconnect`.

## Novedades en v1.8.1

- **180 docstrings** añadidos a lo largo del código fuente para documentación interna completa.
- **Integración pytest-cov** con baseline de cobertura del 14%.
- **Mypy type checking** habilitado para verificación estática de tipos.
- **Persistencia de quota** en `config.json` (`quota_cache`) para evitar consultas innecesarias.
- **Advertencia de quota baja** cuando la quota disponible supera el 90% de uso.
- **Modo offline**: indicador visual "stale" cuando la quota proviene de caché y no hay conexión.
- **ruff auto-fix aplicado**: 135 issues corregidos automáticamente.

## Requisitos

- Linux (Ubuntu/Debian, Zorin OS, etc.)
- [rclone](https://rclone.org/) v1.65+ (se instala automáticamente con el .deb)
- Python 3.10+ y PyQt6 (se instalan automáticamente como dependencias del .deb)

## Instalación

### Paquete .deb (recomendado)

```bash
sudo dpkg -i syncmaster_1.9.0_amd64.deb
```

El instalador configura automáticamente todas las dependencias:
- `python3 >= 3.10` y `python3-pyqt6` se instalan vía apt si faltan.
- `rclone >= 1.65` se descarga e instala desde rclone.org si no está presente o es una versión anterior.

Para ejecutar:

```bash
syncmaster
```

O desde el menú de aplicaciones: buscar "SyncMaster".

### Desde fuente

```bash
git clone git@github.com:ferdcard-ux/SyncMasterPython.git
cd SyncMaster-Bunker
pip install -r requirements.txt
python main.py
```

## Guía de configuración

1. Al iniciar por primera vez la app no muestra servicios. Ir a **Configuración → Servicios**.
2. Habilitar los servicios deseados (Google Drive, OneDrive, LocalSync).
3. Para servicios en la nube, usar el botón **"Configurar RClone"** para crear el remote correspondiente vía `rclone config`.
4. Completar: Directorio Local, Directorio Remoto (`nombre_remote:/path`), Intervalo, Modo.
5. Guardar. Los servicios aparecen en la ventana principal con su estado en tiempo real.

### Modos de sincronización

| Modo | Descripción |
|------|-------------|
| `bisync` | Sincronización bidireccional con detección de conflictos |
| `copy` | Solo subida (local → remoto) |
| `sync` | Espejo unidireccional (remoto = local) |

### Indicadores de estado

Cada tarjeta de servicio muestra un anillo de progreso que cambia de color según el estado:

| Estado | Color | Comportamiento |
|--------|-------|----------------|
| Sincronizando / Escaneando | `#04F8F5` (cian) | Arco animado + porcentaje debajo del texto |
| En espera | `#C1F804` (verde lima) | Parpadeo cada 800ms |
| Sincronizado / Activo | `#4CAF50` (verde) | Sólido, sin animación |
| Pausado | `#f7e05f` (amarillo) | Sólido |
| Advertencia / Limitado | `#FF9800` (naranja) | Sólido; no sobrescribe "Sincronizando" |
| Error / Sin conexión | `#F44336` (rojo) | Sólido |

### Información de quota

Cada tarjeta muestra una segunda columna con datos de quota del proveedor:

| Campo | Descripción |
|-------|-------------|
| Total | Espacio total disponible |
| Used | Espacio utilizado |
| Free | Espacio libre |
| Trashed | Archivos en papelera |

La quota se obtiene de `rclone about --json <remote>:` al iniciar y después de cada sincronización exitosa.

## Arquitectura

### Componentes principales

- **`RcloneServiceManager`**: Manager genérico para cualquier remote rclone. Usa `ProcessWorker` (QThread) para ejecutar comandos sin bloquear la UI.
- **`OneDriveManager`**: Migrado a RClone completo (bisync/copy/sync) con auto-recuperación y detección de errores.
- **`GDriveManager`**: Gestión específica de Google Drive con chunks optimizados y deduplicación.
- **`LocalSyncManager`**: Sincronización entre dos directorios locales.
- **`SyncCoordinator`**: Previene sincronizaciones simultáneas del mismo directorio mediante locks por ruta.
- **`ConfigManager`**: Persistencia en `~/.config/syncmaster/config.json`.

### Seguimiento de progreso

- Cualquier línea de rclone con `%` actualiza el arco de progreso.
- El porcentaje se preserva a través de eventos de advertencia/error.
- Anti-flickering: líneas con `0%` transitorio no resetean el progreso real.
- Bisync usa `--stats 1s --stats-one-line` en lugar de `--progress` para mantener visibles las estadísticas.

### Auto-recuperación

Si `rclone bisync` detecta un error crítico:
1. Marca `needs_resync = True`.
2. En el próximo ciclo ejecuta `--resync`.
3. Si el `--resync` falla, limpia los `.lst` corruptos y reintenta.

## Configuración

Archivos en `~/.config/syncmaster/`:

| Archivo | Propósito |
|---------|-----------|
| `config.json` | Configuración de servicios, intervalos, modos |
| `rclone_filters.txt` | Patrones de exclusión global |

## Logs

```
~/.config/syncmaster/logs/syncmaster-YYYY-MM-DD.log
```

Se mantienen los últimos 3 días. Cada línea incluye timestamp, nivel, archivo:línea y mensaje.

## Licencia y derechos

Esta obra es propiedad exclusiva de Miguel Fernando Cárdenas Alvear (FerDev). Se entrega bajo la denominación "Evaluación Privada / Propietaria" y no concede permisos para reproducir, distribuir o modificar el software sin autorización escrita.
