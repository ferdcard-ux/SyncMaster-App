# SyncMaster-v1.6.2-Private

**SyncMaster v1.6.1-Private** es un sistema de sincronización seguro y cerrado diseñado para escenarios privados de alta disponibilidad. Esta edición de estabilidad incluye protecciones avanzadas contra fallos silenciosos y optimización de recursos en segundo plano.

## Requisitos de instalación
- Linux de 64 bits (Zorin OS, Ubuntu o similares) con Python 3.10 y PyQt6 disponibles.
- Rclone configurado con los remotos autorizados y, si corresponde, el cliente oficial de OneDrive.
- Acceso de lectura/escritura a los directorios locales y a `~/.config/sync_master`.
- Conexiones seguras (SSH, tokens protegidos, credenciales encriptadas) para los servicios en la nube.

## Guía de configuración local
1. **Servicios**: utiliza el diálogo de configuración para definir Local, Google Drive, OneDrive y demás servicios Rclone. Establece directorios, intervalos y modos (bisync/copy/sync).
2. **Exclusiones**: las exclusiones se ingresan línea a línea y se traducen directamente en parámetros `--exclude` de Rclone en tiempo de ejecución.
3. **Estado y botones**: cada tarjeta muestra estado, modo, intervalo y última sincronización; el botón global “Sincronizar servicios” sólo ejecuta gestores activos que no estén pausados.
4. **Protecciones**: el software ignora lockfiles, reprende `Quota exceeded` con un modo `Limitado (API)` en naranja y pausa los ciclos cinco minutos antes de reanudar.

## Manual del usuario
- Ejecuta `SyncMaster-v1.6.0-Private.AppImage` para abrir la interfaz protegida.
- La bandeja del sistema permite iniciar la app, limpiar la consola o ejecutar sincronizaciones manuales.
- El monitor de actividad (Mini-Log) permite ver las últimas 10 líneas con auto-ajuste y fuente de 12pt.
- Las tarjetas tienen un botón Pausar/Reanudar y reflejan el modo activo (bisync/copy/sync) con iconos especiales.

## Licencia y derechos
Esta obra es propiedad exclusiva de Miguel Fernando Cárdenas Alvear (FerDev). Se entrega bajo la denominación “Evaluación Privada / Propietaria” y no concede permisos para reproducir, distribuir o modificar el software sin autorización escrita.

## Cambios recientes (v1.6.0)
- **Dashboard Inteligente**: Widgets circulares con puntas redondeadas, carril de fondo y gramática reactiva ("Sincronizando" -> "Sincronizado" con colores atados).
- **Filtros Globales y Portabilidad**: Generación automática de `rclone_filters.txt` y silenciado de symlinks mediante `--skip-links` para un monitoreo limpio.
- **Visualización Premium**: Contadores color-coded sincronizados con el lenguaje visual de los estados y mini-log ensanchado +60% para máxima legibilidad.
