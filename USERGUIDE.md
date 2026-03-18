# Sync Master User Guide

## Introducción
Sync Master es un panel de monitoreo y orquestación para sincronización de carpetas locales y servicios en la nube (Rclone, Google Drive, OneDrive, Mega). La interfaz Dark prioriza contraste, confirma estado y controla eventos críticos como errores, `lockfile` y límites de API.

## Características principales
- Tema Dark con tipografía +1 pt en controles y +2 pt en la consola de logs, tarjetas gris pizarra (#2D2D2D) y fondo gris carbón (#1E1E1E). Botones con bordes finos, enfoque visible y estados dinámicos por servicio.
- Trifecta de modos por servicio (bisync/copy/sync). Cada servicio muestra un sello con iconos ↔, ↑ o ⇄ en su tarjeta y un descriptor del modo actual.
- Logs inteligentes que filtran metadatos ruidosos (Modtime, HashType, Building Path, etc.) y muestran sólo eventos relevantes (transferencias, notices, errores). Cuando no hay actividad visible aparece `[Servicio] En ejecución....`.
- Limpieza selectiva de caché Rclone con diálogo de casillas y opción de re-sincronizar o programar `--resync`.
- Protección a errores frecuentes: ignorar `cannot remove lockfile ... no such file or directory`, reintentos automáticos, y detección de `Quota exceeded` para pausar servicios 5 minutos y cambiar el estado a `Limitado (API)`.
- Guardias Rclone para la nube: `--transfers 2`, `--checkers 4`, `--tpslimit 5`, y `--drive-chunk-size 64M` cuando se sincroniza con Google Drive.

## Modos de uso
1. **Sincronización periódica**: cada servicio configura su intervalo (minutos). Los servicios locales (incluyendo Rclone) lanzan automáticamente el proceso según ese cron. El botón `Sincronizar servicios` fuerza manualmente ese lanzamiento para todos los servicios activos que no estén pausados ni deshabilitados.
2. **Pausar/Reanudar**: cada tarjeta tiene el botón `Pausar`/`Reanudar`. En pausa se vuelve amarillo y el texto cambia. Mientras está pausado no se ejecutan cron ni sincronizaciones manuales.
3. **Modo Standby del log**: la consola muestra un placeholder con `[Servicio] En ejecución....` hasta que llega un mensaje considerado relevante. Los mensajes ignoran los ruidos en JSON y `Building path`.
4. **Gestión de caché Rclone**: el diálogo permite elegir servicios específicos (Local, GDrive, OneDrive y Mega-Dev). Tras limpiar la caché se pregunta si resincronizar; si se responde “No”, se coloca `--resync` automáticamente para la próxima ejecución.

## Configuración por servicio
- **Modalidades**: via `Settings > Google Drive` o `Servicios Rclone` se selecciona `bisync`, `copy` o `sync`, cada uno con tooltip explicativo. El manager construye el comando `rclone bisync|copy|sync ...` añadiendo los flags globales `--min-age 30s`, `--local-no-check-updated` y las exclusiones definidas en el campo de texto.
- **Exclusiones**: cada línea del campo de exclusiones se agrega al comando con `--exclude`. Por ejemplo:
  ```text
  *.tmp
  node_modules/**
  Path /.cache/
  ```
  se traduce en `--exclude *.tmp --exclude node_modules/** --exclude Path /.cache/`.
- **Intervalos y directorios**: define el directorio local y remoto, el intervalo en minutos, y si aplica, el propósito del servicio en la nube. También puedes agregar servicios Rclone personalizados usando la pestaña correspondiente.

## Manejo de errores y estados
- **Lockfiles**: si la salida menciona `lockfile`, el exit code 1 se considera exitoso; el panel vuelve a `Activo` tras la sincronización y se registra `Error de lockfile ignorado...`.
- **API limitada**: si se detecta `Quota exceeded`, el servicio pasa a `Limitado (API)` (texto naranja), se muestra `[Servicio] API Saturada...`, se detiene el cron por 5 minutos y se vuelve a `Activo` al terminar el backoff.
- **Auto-recuperación**: cuando se requiere `--resync` por errores críticos, se añade automáticamente y se reejecuta la tarea; los modos `copy`/`sync` sólo reinician sin forzar `--resync` a menos que el usuario lo programe.

## Arquitectura del Sistema
Sync Master funciona como un wrapper propietario en Python sobre los binarios de Rclone y los clientes de nube. La UI (PyQt6) controla cada proceso mediante `QProcess`, capta stdout/stderr, limpia el ruido y decide si reintentar, pausar o activar protecciones (`--min-age 30s`, `--transfers 2`, `--tpslimit 5`). El wrapper mantiene la coherencia entre el cron interno y las tarjetas de servicio, reprogramando `--resync` cuando detecta abortos críticos y pausando 5 minutos cuando la API devuelve `Quota exceeded`.

El código también asegura que cada servicio tenga su propio estado (`Activo`, `Sincronizando`, `En Espera`, `Limitado (API)`) y que los cambios de modo (bisync/copy/sync) se propaguen desde `settings_dialog.py` hasta los comandos de Rclone. La ventana de monitoreo cubre todos los mensajes que pasan por el wrapper y solo expone los eventos relevantes.

## Documentación y licencia de evaluación
La entrega privada incluye `COPYRIGHT.txt`, `TERMS.md` y este `USERGUIDE.md`. El software se reparte bajo una Licencia de Evaluación Académica para instructores del SENA, que mantiene todos los derechos reservados y prohíbe redistribuciones sin autorización. La documentación explica cómo se integra Python con Rclone, las decisiones de diseño y el modelo de control original que respalda la interfaz propietaria.

## Recomendaciones de despliegue
1. Valida el binario `SyncMaster-v1.5.6-Private.AppImage` dentro del entorno autorizado antes de entregarlo a los instructores SENA.
2. Revisa que las credenciales (tokens, SSH, `.env`) se mantengan fuera de los controles de código (ver `.gitignore`).
3. Mantén la configuración de exclusiones y modos en `~/.config/sync_master/config.json`; la aplicación la sobrescribe cada vez que guardas.

## Soporte y seguimiento
Si hay incidencias, documenta el mensaje exacto del log y compártelo con el instructor principal o el responsable académico. La bandeja del sistema ofrece notificaciones críticas o advertencias para detectar errores de control, y la consola rastrea sólo las líneas que justifican una intervención.
