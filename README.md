# SyncMaster App

![Licencia: GPL v3](https://img.shields.io/badge/Licencia-GPLv3-blue.svg)
![Version](https://img.shields.io/badge/Version-v1.5.4-blue)
![Plataforma](https://img.shields.io/badge/Plataforma-Linux-informational)

SyncMaster es una aplicacion de sincronizacion de archivos enfocada en simplicidad y confiabilidad, distribuida como AppImage para Linux.

## Caracteristicas principales
- Sincronizacion bidireccional entre equipos y la nube.
- Iconos dinamicos que reflejan el estado de la sincronizacion en tiempo real.
- Bandeja del sistema para iniciar, pausar y ver el estado rapidamente.
- Configuracion simple de carpetas locales y remotas.
- Portabilidad total con AppImage (sin instaladores complejos).

## Novedades de v1.5.4
- **Interfaz Dark mejorada**: toda la UI ahora usa un fondo Gris Carbón (#1E1E1E) y tarjetas Gris Pizarra (#2D2D2D) con tipografía más grande (+1 pt en controles, +2 pt en el log) y botones de borde sutil que conservan contraste en reposo, enfoque y hover.
- **Monitor de estado enriquecido**: cada servicio reporta “Estado: Sincronizando” (ámbar) cuando lanza tareas y “Estado: En espera” (amarillo) mientras aguarda recursos; los botones de pausa usan amarillo mientras el servicio está detenido para no perder visibilidad.
- **Sincronización manual visible**: el botón “Sincronizar servicios” refleja el foco del tema Dark, marca el estado “Sincronizando” en los servicios listos y deja claro en la sección de estado qué servicios están ejecutándose.
- **Log inteligente y standby**: el panel de actividad limpia automáticamente metadatos (Modtime, HashType, Building Path, etc.), muestra solo transferencias/Deleted/NOTICE/errores y mantiene un mensaje `[Servicio] En ejecución....` hasta que aparece nueva actividad relevante.
- **Gestión inteligente de caché RClone**: la limpieza abre un diálogo con casillas por servicio (Local, GDrive, OneDrive y Mega-Dev), pregunta si re-sincronizar ahora y, si se opta por “No”, programa internamente `--resync` para la próxima ejecución.
- **Robustez frente a lockfiles**: los comandos RClone incluyen `--min-age 30s` y `--local-no-check-updated`, ignoran el error `cannot remove lockfile ... no such file or directory` y consideran la tarea exitosa si ese es el único fallo, manteniendo el estado en “Activo”.

## Como instalar en Linux
1. Descarga la AppImage desde la seccion de Releases.
2. Dale permisos de ejecucion:

```bash
chmod +x SyncMaster-*.AppImage
```

3. Ejecuta la aplicacion:

```bash
./SyncMaster-*.AppImage
```

## Requisitos
Para ejecutar AppImages en distribuciones modernas (como Zorin o Ubuntu), solo necesitas FUSE instalado.

Si tu distribucion requiere soporte FUSE para AppImage, instala el paquete correspondiente antes de ejecutar.

## Releases
Descargas y notas de version en:
Releases: https://github.com/ferdcard-ux/SyncMaster-App/releases

## Creditos
SyncMaster esta desarrollado con un enfoque multiplataforma y un empaquetado pensado para entornos Linux.

## Términos de Uso y Descargo de Responsabilidad (GNU GPL v3)

Al utilizar o modificar **Sync Master**, aceptas los siguientes términos:

1. **Garantía y Responsabilidad**: Según lo estipulado en las secciones 15, 16 y 17 de la Licencia GPL v3, este software se proporciona "tal cual", sin garantía de ningún tipo. El desarrollador no es responsable de cualquier daño o pérdida de datos derivados de su uso.
2. **Filosofía Open Source**: Cualquier versión derivada o modificación que decidas distribuir debe ser publicada bajo esta misma licencia (GPL v3), garantizando que el software siga siendo libre para todos.
3. **Privacidad de Datos**: Sync Master opera localmente. Tus credenciales de GDrive, OneDrive, Mega y cualquier otro servicio que decidas configurar, son gestionadas por Rclone o El cliente de OneDrive para Linux y almacenadas exclusivamente en tu sistema local.
4. **Cumplimiento con Terceros**: Eres responsable de asegurar que tu uso de esta herramienta cumple con los términos de servicio de los proveedores de almacenamiento en la nube.