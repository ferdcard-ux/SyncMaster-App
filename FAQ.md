# ❓ Preguntas Frecuentes (FAQ) - Sync Master v1.9.0
**Soporte Técnico y Operativo de la Solución FerDev**

## 1. ¿Qué significan los iconos en el "Modo" de cada tarjeta?
Los iconos representan la dirección del flujo de tus datos:
* **Bisync ↔:** Sincronización completa. Los cambios en tu carpeta local se suben a la nube y los cambios en la nube se bajan a tu PC.
* **Sync ↓:** Espejo unidireccional. La nube se ajusta para ser una copia exacta de tu PC, incluyendo la eliminación de archivos en la nube si los borras localmente.
* **Copy ↑:** Respaldo de seguridad. Los archivos nuevos o modificados se suben, pero nunca se borran archivos de la nube, protegiéndote contra borrados accidentales en tu PC.

## 2. La aplicación dice "Estado: Limitado (API)" en color naranja. ¿Se rompió algo?
No, es una función de protección activa. Significa que el proveedor de nube (como Google Drive) ha alcanzado su límite de peticiones por segundo (Quota exceeded, Error 429 o rate limit). Sync Master reduce automáticamente el ritmo de transferencia (transfers/checkers: 2/4 → 1/2 → 1/1) y reintenta en unos minutos; el nivel elegido se recuerda en `config.json` y se recupera solo cuando la API lo permite.

## 3. ¿Por qué algunos servicios dicen "Rclone" y otros "on-prem"?
Es una distinción de la tecnología utilizada para conectar:
* **(Rclone):** Utiliza el motor de Rclone para gestionar la transferencia (ej. Google Drive o Mega).
* **(on-prem):** Utiliza un cliente de sincronización local o nativo instalado en tu sistema (como el agente de OneDrive).

## 4. ¿Cómo sé que el motor sigue activo después de horas de sincronización?
Hace poco la app reforzó su limpieza del `ProcessWorker`: cada servicio detiene su worker anterior con `stop()` y espera con `wait()` antes de crear uno nuevo, así Qt nunca libera el hilo mientras se espera. Durante pruebas largas se generan logs como `DEBUG: Detectado 42% para Mega-Dev` cada segundo; si ves esa huella en `~/.config/sync_master/crash.log` o si `main.py` emite esos `DEBUG` en tu terminal, estás viendo que el worker sigue recibiendo información y la app no murió silenciosamente.

## 5. ¿Puedo sincronizar carpetas de programación sin subir archivos pesados como "node_modules"?
Sí, mediante las **Exclusiones Globales** (que la app genera automáticamente en `~/.config/sync_master/rclone_filters.txt`) se ignoran reglas estándar como basura y cachés. Además, puedes añadir tus propios patrones en la configuración de cada servicio para ignorar `node_modules/**` o `target/**` de forma sumarizada.

## 6. ¿Qué hago si un servicio se queda en "Error" de forma persistente?
La causa más común es un archivo de bloqueo (lockfile) que no se pudo borrar tras un corte de luz o de internet.
- Haz clic en el botón [Limpiar Caché RClone] en la barra inferior.
- Selecciona el servicio que falla y confirma la limpieza.
- La app te preguntará si deseas realizar una Re-sincronización (--resync); selecciona "Sí" para reconstruir la base de datos de archivos de forma segura.

## 7. ¿La aplicación debe estar abierta para que funcione?
Sí, pero puedes activar la opción de `Inicio Automático` en la pestaña General. Esto permitirá que la app se inicie con tu sistema y se mantenga trabajando silenciosamente desde la bandeja de notificaciones (System Tray).

## 8. ¿Es seguro usar Sync Master con mis cuentas personales?
Totalmente. Sync Master es una solución propietaria privada que no almacena tus contraseñas; utiliza tokens de acceso seguro (OAuth) a través de Rclone y respeta las políticas de seguridad de Google y Microsoft.

## 9. ¿Qué sucede si pierdo la conexión a internet mientras sincronizo?
El sistema Connectivity Guard detectará la pérdida de conexión y detendrá los intentos de subida para evitar errores innecesarios o bucles de re-sincronización fallidos. Una vez que internet regrese, la app retomará sus ciclos programados normalmente.

## 10. ¿Cómo instalo el paquete .deb en Zorin OS / Debian / Ubuntu?
El entregable de v1.9.0 es un `.deb` nativo:
* **Instalar:** `sudo dpkg -i syncmaster_1.9.0_amd64.deb` y luego `sudo apt-get install -f` si hay dependencias pendientes.
* **Dependencias automáticas:** el instalador instala `python3-pyqt6` vía apt y descarga `rclone >= 1.65` desde rclone.org si no está presente.
* **Ejecutar:** escribe `syncmaster` en la terminal o búscalo en el menú de aplicaciones como "SyncMaster".

## 11. ¿Cómo uso el botón "Montar/Desmontar" de una tarjeta cloud?
El botón expone tu carpeta remota como un punto de montaje FUSE (unidad local) usando `rclone mount`. Al pulsar "Montar" la carpeta aparece en `~/.syncmaster/mounts/<servicio>/`; al pulsar "Desmontar" se libera. Al cerrar la aplicación todos los puntos de montaje activos se desmontan automáticamente. Requiere permisos de FUSE (por defecto en las distros actuales).

## 12. ¿Qué muestra cada contador del panel de monitoreo?
* **Archivos Completados:** cuenta archivos realmente transferidos (Copied/Updated/Moved/Renamed); al pulsarlo verás la lista de nombres por servicio.
* **Advertencias:** líneas de advertencia/retry del log; al pulsarlo verás cada línea original.
* **Errores:** líneas de error crítico; al pulsarlo verás cada línea original.
Los números ya no dependen del porcentaje del anillo, solo de eventos reales del log.

## 13. ¿Puedo usar mi propio Client ID en Google Drive o OneDrive?
Sí. En la configuración de GDrive, OneDrive o servicios Rclone pulsa **"Usar tu propio Client ID (reconectar)"**, pega tu Client ID y Client Secret, y la app los aplica con `rclone config update --all` y abre la reconexión interactiva.

## 14. ¿Cómo agrego un nuevo proveedor de nube (ej. Mega, Dropbox, FTP)?
Sync Master es extensible gracias a su integración con el motor Rclone:
* **Asistente de Configuración:** Ve a [Configuración] > [Agregar Servicios] y usa la opción correspondiente al tipo de servicio que quieras crear.
* **Terminal Interactiva:** Se abrirá una ventana de comandos dentro de la propia aplicación donde podrás elegir el proveedor de una lista dinámica.
* **Autorización:** Sigue los pasos que dicte la terminal (generalmente abrirá tu navegador para que inicies sesión en el servicio elegido).
* **Exclusiones por proveedor:** el nuevo servicio recibe presets de exclusión por defecto adaptados a su proveedor.
* **Finalización:** Una vez configurado en la terminal, el nuevo servicio aparecerá automáticamente como una tarjeta en tu panel principal y como una nueva pestaña de configuración para ajustar sus carpetas y exclusiones.
