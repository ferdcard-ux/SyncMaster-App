# Registro de Cambios - Sync Master

## [1.5.6] - 2026-03-18
### Añadido
- **Licencia privada y documentación académica**: se eliminó el texto GPL, se introdujo el archivo `COPYRIGHT.txt`, `TERMS.md` describe la Licencia de Evaluación Académica para instructores SENA y `USERGUIDE.md` ahora contiene la arquitectura del wrapper propietario sobre Rclone.
### Reemplazado
- **Marca y brand privado**: `README.md` se enfocó en requisitos de instalación y manuales internos, se actualizó `version.py` a v1.5.6 y se ajustó la ventana Info para mencionar el branding propietario, sin referencias públicas.
### Mejorado
- **Seguridad y secretos**: `.gitignore` bloquea claves, tokens y archivos `.env`, garantizando que no se filtren credenciales en commits.

## [1.5.5] - 2026-03-17
### Añadido
- **Trifecta de sincronización Copy/Sync/Bisync**: Cada servicio basado en rclone (Local, Google Drive y los servicios personalizados) dispone de un selector que describe impactos y un sello en la tarjeta para mostrar si está en modo bisync, copy o sync (flecha vertical para unidireccional, ↔ para bidireccional). Un ligero ajuste en el padding mantiene el nuevo texto antes del botón de control.
### Mejorado
- **Comandos conscientes del modo**: La generación de comandos incorpora el modo elegido y aplica `--min-age 30s` y `--local-no-check-updated` a la rutina completa; `bisync` sigue soportando `--resync`, mientras que `copy` y `sync` reinician sin ese flag y siguen ignorando lockfiles para no detener la tarea.
- **Monitor con indicadores**: El monitor y las tarjetas ahora refrescan inmediatamente el texto del modo al guardar la configuración, y el selector estilizado del panel de settings (gris pizarra) ofrece tooltips descriptivos para cada opción.
- **Guardia de APIs y concurrencia en la nube**: Los servicios RClone en la nube arrancan con `--transfers 2`, `--checkers 4`, `--tpslimit 5` y, cuando aplica, `--drive-chunk-size 64M`; si RClone responde con `Quota exceeded` pasamos a `Estado: Limitado (API)` (naranja), mostramos `[Servicio] API Saturada...` y pausamos los ciclos durante 5 minutos antes de reanudar automáticamente sin marcar error.

## [1.5.4] - 2026-03-15
### Añadido
- **Tema Dark Renovado**: Toda la interfaz migró a un esquema #1E1E1E / #2D2D2D con tipografía más generosa (+1 pt en la UI, +2 pt en el log) y botones con borde delgado para mantener contraste sin sacrificar legibilidad.
- **Filtro Inteligente y Standby de Logs**: El panel de actividad ahora muestra `[Servicio] En ejecución....` mientras no haya cambios y solo se llena con transferencias, eliminaciones, avisos NOTICE y errores reales; el resto del ruido queda oculto hasta que ocurre una transferencia.
- **La acción “Sincronizar servicios”**: Ahora fuerza el estado “Sincronizando” para cada servicio activo antes de lanzar el `sync`, conserva el efecto de enfoque del botón y vuelve a aplicarlo tras pulsarlo; el botón de “Pausar/Reanudar” usa el estilo amarillo cuando está en pausa y el verde cuando se reactiva.
- **Implementación y monitor de estado**: Para que la interfaz reciba los estados correctos, los gestores `local`, `gdrive`, `onedrive` y cada servicio RClone emiten “Sincronizando” al iniciar un proceso y “En Espera” cuando quedan bloqueados, lo que alimenta correctamente el monitor de estado sin necesidad de tocar los logs.

### Mejorado
- **Gestión Selectiva de Caché RClone**: El botón "Limpiar Cache RClone" abre un diálogo con casillas por servicio (Local, Google Drive, OneDrive, Mega-Dev), borra la caché de bisync, pregunta si desea resincronizar ahora y, si se elige "No", programa el flag `--resync` para la siguiente ejecución automática de cada servicio.
- **Contexto de sincronización más visible**: Cada servicio pasa a reportar “Estado: Sincronizando” cuando arranca y “Estado: En espera” cuando aguarda recursos disponibles, el botón “Sincronizar servicios” actualiza esos estados y mantiene el foco estilo Dark, y los botones “Pausar/Reanudar” usan amarillo mientras el servicio está detenido para mejorar el contraste.
- **Estado y monitor alineados**: El monitor y los gestores ahora pintan “Estado: Sincronizando” en ámbar y “Estado: En espera” en amarillo con una paleta Dark consistente, el botón “Sincronizar servicios” establece ese estado antes de ejecutar los syncs y recupera el foco, y `local`, `gdrive`, `onedrive` y cada servicio RClone generan los estados correctos sin introducir ruido adicional en los logs.
- **Registros completos**: La consola ahora reconoce `onedrive` como término de evento clave, de modo que las entradas del servicio OneDrive siempre llegan al log; al mismo tiempo la tolerancia a `lockfile` solo exige que alguna línea de error lo mencione para tratar el `exit code 1` como éxito cuando ese es el único problema.
- **OneDrive con estados completos**: El servicio OneDrive marca `Estado: Sincronizando` durante la actividad detectada y, tras unos segundos de inactividad, vuelve automáticamente a `Estado: Activo`, lo que enseña en el tablero que la sincronización finalizó aun cuando el binario siga ejecutándose en segundo plano.
- **Auto-sanación y tolerancia Rclone**: Cada ciclo vuelve el estado visible a `Activo`, los comandos de bisync incluyen `--min-age 30s` y `--local-no-check-updated`, y los errores de "cannot remove lockfile ... no such file or directory" ya no rompen la tarea (el `exit code 1` se ignora cuando ese es el único fallo); OneDrive, Local, GDrive y los servicios Rclone ahora preparan el flag `--resync` cuando se solicita y lo ejecutan sólo cuando es necesario.

### Parche
- **Logs visibles y lockfiles tolerados**: el monitor acepta entradas etiquetadas como `[OD]`, `[OD Info/Err]`, `[OD Prompt]` y variantes para que OneDrive aparezca en la consola, y el servicio RClone deja de marcar “Error (Código 1)” si el único mensaje menciona `lockfile`.

## [1.5.2] - 2026-03-13
### Añadido
- **Iconos en Botones**: Se agregaron iconos a los botones principales para mejorar la identificación rápida.

### Mejorado
- **Estilo Global de Botones**: Fondo oscuro uniforme con texto blanco, hover más intenso, enfoque visible y texto centrado en toda la app.
- **Pestañas de Configuración**: Mayor altura para evitar cortes de texto y efecto hover en las pestañas.
- **Botón Pausar/Reanudar**: Mantiene el dinamismo de color e incluye icono acorde al estado.

## [1.5.1] - 2026-03-13
### Añadido
- **Diálogo de Bienvenida**: Se muestra en la primera ejecución con información legal y de dependencias (RClone y OneDrive).

### Mejorado
- **Estilo Unificado de Botones**: Todos los botones comparten el mismo color base; el botón Pausar/Reanudar cambia dinámicamente cuando está en pausa.
- **Info Integrado**: El botón "Info" se reubicó en la barra inferior de controles y se eliminó la barra superior adicional.
- **Configuración Rclone**: Cada servicio agregado crea su pestaña de configuración entre Google Drive y Servicios Rclone.

## [1.5.0] - 2026-03-13
### Añadido
- **Panel de Servicios Dinámico (Rclone)**: Los servicios Rclone agregados ahora aparecen como tarjetas de sincronización en el panel principal, con registro de actividad y controles completos.
- **Botón Info**: Nueva ventana informativa con detalles de la app (nombre, versión, fecha, desarrollador y contacto).
- **Pausar/Reanudar Sincronizaciones**: Control global para detener o reanudar todas las tareas de sincronización desde la interfaz principal.

### Mejorado
- **Configuración**: La pestaña "General" se mantiene siempre al final del menú de Configuración.
- **Rclone Config Interactivo**: La terminal de configuración se inicia automáticamente al añadir un servicio, permanece abierta durante el proceso y solo permite guardar al finalizar.
- **Confirmaciones de Seguridad**: Advertencias antes de limpiar la caché de Rclone y al eliminar servicios Rclone (incluye terminal interactiva).
- **Estilo de Botones**: Colores diferenciados para "Limpiar Cache RClone" y "Limpiar Consola".

## [1.4.8] - 2026-03-12
### Añadido
- **Configuración de Nuevos Servicios Rclone**: 
  - Se ha añadido una nueva pestaña "Servicios Rclone" en la ventana de Configuración para gestionar servicios de sincronización basados en Rclone.
  - Se ha creado un nuevo diálogo "Añadir Servicio Rclone" que permite al usuario nombrar un nuevo servicio, seleccionar un proveedor de nube de una lista obtenida dinámicamente de Rclone, y asignar un directorio local.
  - Se ha integrado un **terminal interactivo** dentro del diálogo para que el usuario pueda completar el proceso de configuración de `rclone config` sin salir de la aplicación.

## [1.4.7] - 2026-03-12
### Añadido
- **Claridad en la Interfaz**: Se ha añadido un sufijo al nombre de cada servicio en el panel principal para indicar la tecnología de sincronización que utiliza (ej. "Google Drive (Rclone)", "OneDrive (on-prem)").

## [1.4.6] - 2026-03-12
### Añadido
- **Limpieza de Caché de Rclone**: Se ha añadido un botón "Limpiar Cache RClone" en la interfaz principal. Esta función permite al usuario eliminar de forma segura la caché de `rclone bisync` y fuerza una re-sincronización (`--resync`) en todos los servicios basados en Rclone (Local y GDrive) para resolver estados de error persistentes.

## [1.4.5] - 2026-03-12
### Añadido
- **Deduplicación Automática (GDrive)**: Se ha verificado la función existente que detecta y corrige automáticamente los archivos duplicados en Google Drive ejecutando `rclone dedupe`, mejorando la integridad de los datos.

## [1.4.4] - 2026-03-12
### Corregido
- **Notificaciones del Sistema**: Se ha reparado el sistema de notificaciones, que no se iniciaba correctamente debido a un error en el orden de inicialización de los componentes en `main.py`. Ahora las alertas de error y advertencia funcionan como se esperaba.

## [1.4.3] - 2026-03-12
### Corregido
- **Sincronización Local (Rclone bisync)**: Se verificó y confirmó la función que detecta y elimina automáticamente el archivo de bloqueo `.ick` de la caché de Rclone, permitiendo una recuperación automática mediante re-sincronización.

## [1.4.2] - 2026-03-13
### Añadido
- **Notificaciones del Sistema**: Ahora se muestran notificaciones integradas del sistema para errores críticos y advertencias de sincronización, alertando al usuario sobre problemas importantes.



Todos los cambios notables en este proyecto serán documentados en este archivo.

## [1.4.1] - 2026-02-20
### Corregido
- **OneDrive**: Se corrigió el conflicto entre los flags `--force` y `--resync` que impedía la recuperación de errores.
- **OneDrive**: Se restauraron las exclusiones por defecto (`*.tmp`, `~*`, etc.) que se perdían al usar exclusiones personalizadas, evitando advertencias y sincronizaciones innecesarias de archivos temporales.

## [1.4.0] - 2026-02-20
### Añadido
- **Exclusiones de Sincronización**: Nueva capacidad para excluir archivos y carpetas mediante patrones y comodines para todos los servicios (Local, GDrive y OneDrive).
- **Ayuda en Interfaz**: Se agregaron ejemplos de formato y descripciones en la configuración para facilitar el uso de patrones de exclusión.

## [1.3.6] - 2026-02-20
### Corregido
- **OneDrive**: Se corrigió un error de "Malformed config line" asegurando que todos los valores numéricos en el archivo de configuración estén correctamente encerrados entre comillas dobles, como requiere el parser del cliente.

## [1.3.5] - 2026-02-20
### Corregido
- **OneDrive**: Se corrigió un error crítico donde se pasaban argumentos de línea de comandos no soportados (`--connect-timeout`), lo que causaba el fallo inmediato del servicio. Estos parámetros han sido movidos correctamente al archivo de configuración.

## [1.3.4] - 2026-02-20
### Añadido
- **Connectivity Guard**: Nuevo sistema de verificación proactiva que comprueba el acceso a los servidores de Google y Microsoft antes de iniciar cualquier sincronización, evitando fallos por falta de internet.

### Corregido
- **Estabilidad de Red**: Mejora en la lógica de recuperación para evitar bucles infinitos durante cortes de conexión prolongados.
- **Optimización de OneDrive**: Ajuste de tiempos de espera para reducir errores de timeout en redes inestables.

## [1.3.3] - 2026-02-20
### Corregido
- **Bucle de Sincronización**: Se implementó una lógica defensiva en GDrive y OneDrive para evitar bucles infinitos de "resync" cuando falla la conexión.
- **OneDrive**: Se incrementaron drásticamente los tiempos de espera (timeout) y se optimizó la configuración de red para mayor estabilidad.
- **GDrive**: Mejor detección de errores de red durante procesos de recuperación.

## [1.3.2] - 2026-02-20
### Corregido
- **Cierre Inesperado**: Se corrigió un error crítico que provocaba el cierre de la aplicación al intentar registrar mensajes de error en la consola.

## [1.3.1] - 2026-02-20
### Añadido
- **Resaltado de Errores**: Los mensajes de error en el monitor de registros ahora se muestran en color rojo para una identificación rápida.

### Corregido
- **OneDrive**: Optimización de la configuración (reducción de hilos) para mejorar la estabilidad en sistemas con pocos núcleos.
- **OneDrive**: Mejora en la persistencia de conexión.

## [1.3.0] - 2026-02-20
### Añadido
- **Rediseño de Interfaz**: Renovación completa de la GUI a un tema claro con fondo blanco y texto negro.
- **Temas Adaptables**: Los colores de la interfaz ahora se integran mejor con el tema del sistema.
- **Mejora Visual**: Actualización de la consola de registro y tarjetas de servicio para una mejor legibilidad.
- **Botones Modernos**: Se agregaron estilos de botones con colores de estado (azul para configuración, rojo para salir) y efectos de hover.

## [1.2.0] - 2026-02-20
### Corregido
- **Sincronización Local**: Se agregó el flag `--checksum` a `rclone bisync` para evitar bucles infinitos cuando el contenido del archivo no ha cambiado pero las marcas de tiempo difieren.
- **OneDrive**: Se agregó `--no-remote-delete-prevention` para omitir los bloqueos de seguridad al eliminar o mover grandes volúmenes de datos.
- **OneDrive**: Se agregó `--force-http-11` al comando `onedrive` para evitar advertencias y errores relacionados con HTTP/2 en versiones antiguas de `libcurl`.
- **Google Drive**: Se mejoró el manejo de errores para ignorar fallos de red ("unreachable", "timeout") al activar la auto-recuperación, evitando bucles de re-sincronización fallidos.
- **Notificaciones**: Se redujo el ruido filtrando advertencias conocidas de `libcurl` en la consola de registro.

### Añadido
- Sistema de numeración de versiones de la aplicación.
- Visualización del número de versión en el título de la ventana principal.
- Este archivo `CHANGELOG.md`.

## [1.1.0] - Anterior
### Corregido
- Problemas de congelamiento y cierre de la GUI durante la reanudación de la sincronización.
- Bucle de recursión infinita en la lógica de sincronización.

### Añadido
- Soporte para reanudación de sincronización.
- Icono en la bandeja del sistema con operación en segundo plano.
- Consola de actividad en tiempo real.

## [1.0.0] - Lanzamiento Inicial
### Añadido
- Administradores de sincronización independientes para Local, Google Drive y OneDrive.
- Panel de control con tarjetas de estado de servicio.
- Sistema de configuración para intervalos de sincronización y directorios.
