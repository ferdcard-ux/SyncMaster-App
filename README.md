# Sync Master Privado v1.5.6

Sync Master es una solución propietaria para despliegues privados y académicos creada por Miguel Fernando Cárdenas Alvear (FerDev). Esta edición se distribuye bajo la Licencia de Evaluación Académica diseñada para instructores del SENA y no admite contribuciones públicas ni redistribución no autorizada.

## Requisitos de Instalación
- Linux de 64 bits (Zorin OS, Ubuntu o distribuciones similares) con Python 3.10 y PyQt6 instalados.
- Rclone configurado con los remotos autorizados, y el cliente de OneDrive cuando se requiere sincronización on-prem.
- Acceso a los directorios locales y a `~/.config/sync_master` para guardar los ajustes.
- Conexiones seguras (SSH/Rclone tokens) para los servicios en la nube del proyecto.

## Guía de Configuración Local
1. **Servicios principales**: usa el diálogo de configuración para habilitar cada servicio, definir directorios, intervalos y elegir modo (bisync/copy/sync). Las exclusiones se escriben línea a línea y se traducen automáticamente en parámetros `--exclude`.
2. **Monitor de estado**: cada tarjeta muestra estado, modo, intervalo y última sincronización; el botón local ofrece Pausar/Reanudar y el botón global inicia sincronizaciones en los servicios activos.
3. **Protecciones adicionales**: el sistema bloquea ejecuciones mientras la API está limitada, limpia cachés seleccionados con opción para programar `--resync` y mantiene una consola filtrada de eventos relevantes.
4. **Documentación interna**: consulta `USERGUIDE.md` para revisar la arquitectura del sistema, el wrapper propietario sobre Rclone y cómo se gestiona el control de flujo desde Python.

## Manual de Usuario
- Ejecuta `SyncMaster-v1.5.6-Private.AppImage` para abrir la interfaz segura.
- La bandeja del sistema permite iniciar el programa, forzar sincronizaciones o limpiar el log.
- El log recoge sólo transferencias, avisos y errores reales; cuando no hay actividad se mantiene el placeholder `[Servicio] En ejecución....`.
- El botón “Sincronizar servicios” activa los servicios que no estén pausados y no estén deshabilitados; cualquier servicio detenido se marca en amarillo o naranja según el motivo.

## Documentación Académica
Este repositorio mantiene los detalles de autorización y diseño interno en `TERMS.md` y `USERGUIDE.md`, que explican la licencia de evaluación, el wrapper propietario sobre Rclone y los protocolos de control implementados en Python.
