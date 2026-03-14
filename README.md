
# Sync Master (Python)

Esta es la versión reescrita de Sync Master en Python con PyQt6.

## Estructura
El proyecto está contenido en la carpeta `SyncMasterPython`.

## Portabilidad
La AppImage en sí es muy robusta y contiene los binarios necesarios (rclone y onedrive, ya que los incluí en el paquete).

Para mover todo a otro equipo y mantener las cuentas conectadas, debes llevarte:

La Aplicación:
SyncMaster-x86_64.AppImage (El archivo ejecutable).
Configuraciones Críticas (Donde están tus claves): Copia estas carpetas tal cual a la misma ubicación en el nuevo equipo (/home/tu_usuario/.config/):
~/.config/sync_master/ (Configuración general de la App)
~/.config/syncmaster/ (Configuración aislada de OneDrive)
~/.config/rclone/ (Configuración de Google Drive)
Si solo copias la AppImage, funcionará perfecto, pero tendrás que configurar las cuentas de nuevo desde cero.

## Ejecución
Para ejecutar la aplicación directamente sin empaquetar:

```bash
cd SyncMasterPython/AppDir
./AppRun
```

O si prefieres usar el entorno python del sistema directamente:
```bash
cd SyncMasterPython
python3 main.py
```
Asegúrate de tener instaladas las dependencias: `PyQt6`.

## Empaquetado como AppImage
Debido a restricciones del entorno de desarrollo, el archivo `.AppImage` final no se pudo generar automáticamente, pero el directorio `AppDir` está completamente preparado.

Para generar la AppImage final en tu sistema, asegúrate de tener `appimagetool` instalado y ejecuta:

```bash
cd SyncMasterPython
./build.sh
```
(Si falla el `build.sh` incluido, puedes descargar `appimagetool` y correr: `appimagetool AppDir SyncMaster-x86_64.AppImage`)

## Características
- **Interfaz Gráfica Python (PyQt6)**: Moderna y responsiva.
- **Sincronización Independiente**: Temporizadores separados para OneDrive y Google Drive.
- **Configuración**: Selección de carpetas locales y remotas.
- **Bandeja del Sistema**: Minimizar, Restaurar, Sincronizar Todo.
- **Dependencias Incluidas**: Los binarios de `rclone` y `onedrive` se han copiado a `AppDir/usr/bin` para portabilidad.
