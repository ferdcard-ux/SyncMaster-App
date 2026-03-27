## [1.6.0] - 2026-03-27
### Añadido
- **Filtros Globales y Silenciador de Symlinks**: Automatización del archivo `rclone_filters.txt` y flag `--skip-links` para evitar errores técnicos irrelevantes en el panel.
- **Estética Curva y Dashboard Sincronizado**: Los widgets adoptan `RoundCap`, orientación a las 12:00 y los contadores del dashboard se tiñen según su tipo (Completados=Verde, Advertencias=Naranja, Errores=Rojo).

### Mejorado
- **Gramática de Estado**: Transición gramatical "Sincronizando" (Azul) a "Sincronizado" (Verde), centrando milimétricamente los widgets en el layout.
- **Monitor de Actividad**: Reajuste de dimensiones del mini-log (+60% ancho) y tipografía de 12pt para facilitar la lectura rápida.

## [1.5.6] - 2026-03-18
### Añadido
- **Identidad Propietaria FerDev**: la documentación y los avisos legales ( `README.md`, `USERGUIDE.md`, `TERMS.md`, `COPYRIGHT.txt`, `FAQ.md`) definen la solución como una plataforma cerrada de evaluación privada y mantienen los derechos reservados del autor.
### Reemplazado
- **Marca neutra y GUI**: se reescribió el contenido de marca para eliminar menciones institucionales, se actualizó la ventana "Acerca de" y se registró la salida como `SyncMaster-v1.5.6-Private.AppImage` con metadatos propios.

## [1.5.4] - 2026-03-15
### Añadido
- **Interfaz Dark completa**: todos los paneles, tarjetas y controles usan el nuevo esquema Gris Carbón / Gris Pizarra con tipografía ampliada, foco visible y bordes sutiles para los botones.
### Mejorado
- **Estados y logs más claros**: cada servicio ahora expone estados “Sincronizando” y “En espera” con colores ámbar/amarillo, el botón “Sincronizar servicios” dispara dicha actualización y el monitor de actividad filtra ruido, mostrando solo transferencias, avisos NOTICE, errores reales y el placeholder `[Servicio] En ejecución....` cuando no hay cambios.
- **Cache y lockfiles robustos**: la limpieza de caché presenta un diálogo con checkboxes por servicio, pregunta si re-sincronizar al instante y programa `--resync` cuando se elige “No”, mientras que los comandos RClone ejecutan `--min-age 30s` y `--local-no-check-updated`; además, el error `cannot remove lockfile ... no such file or directory` ya no considera la tarea como fallida.
- **Registro de OneDrive y lockfiles**: se amplió la lista de términos significativos para que las trazas de OneDrive lleguen siempre a la consola, y la tolerancia al `lockfile` solo mira si alguna línea de error lo menciona para mantener el servicio activo cuando ese es el único fallo reportado.
- **OneDrive con estados más claros**: Onedrive cambia a `Sincronizando` cuando detecta actividad y vuelve automáticamente a `Activo` después de algunos segundos de silencio, dejando claro en el tablero que la sincronización terminó sin que el cliente se detenga por completo.

## [1.5.5] - 2026-03-17
### Añadido
- **Selector de modos copy/sync/bisync**: Cada tarjeta de servicio muestra ahora un sello con el modo activo y el panel de configuración ofrece un combo estilizado con descripciones para que el paquete técnico sea transparente.
### Mejorado
- **Constructores de comandos sensibles al modo**: Los managers de Local, Google Drive y los servicios Rclone ajustan sus comandos `rclone` según la tríada de modos, reutilizan las protecciones `--min-age 30s` y `--local-no-check-updated`, y restringen `--resync` al modo bisync para evitar resets innecesarios.

## [1.5.2] - 2026-03-13
### Añadido
- **Iconos en Botones**: Se agregaron iconos a los botones principales para mejorar la identificación rápida.

### Mejorado
- **Estilo Global de Botones**: Fondo oscuro uniforme con texto blanco, hover más intenso, enfoque visible y texto centrado en toda la app.
- **Pestañas de Configuración**: Mayor altura para evitar cortes de texto y efecto hover en las pestañas.
- **Botón Pausar/Reanudar**: Mantiene el dinamismo de color e incluye icono acorde al estado.
