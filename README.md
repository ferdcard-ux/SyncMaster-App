# Solución Propietaria FerDev v1.5.6 Privada

Solución Propietaria FerDev es un sistema de sincronización seguro y cerrado diseñado para escenarios privados. Esta edición no admite contribuciones públicas ni redistribución sin autorización; se entrega exclusivamente como Evaluación Privada / Propietaria de FerDev.

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
- Ejecuta `SyncMaster-v1.5.6-Private.AppImage` para abrir la interfaz protegida.
- La bandeja del sistema permite iniciar la app, limpiar la consola o ejecutar sincronizaciones manuales.
- El log filtra ruidos y conserva sólo transferencias, avisos NOTICE, errores y saturaciones de API; cuando no hay actividad se mantiene el mensaje `[Servicio] En ejecución....`.
- Las tarjetas tienen un botón Pausar/Reanudar y reflejan el modo activo (bisync/copy/sync) con iconos especiales.

## Licencia y derechos
Esta obra es propiedad exclusiva de Miguel Fernando Cárdenas Alvear (FerDev). Se entrega bajo la denominación “Evaluación Privada / Propietaria” y no concede permisos para reproducir, distribuir o modificar el software sin autorización escrita.
