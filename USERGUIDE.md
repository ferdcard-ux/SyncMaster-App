# Manual de Usuario: Sync Master v1.9.0
**Desarrollado por Miguel Fernando Cárdenas Alvear (FerDev)** Solución Propietaria de Sincronización de Alta Resiliencia.

---

# 1. Introducción

**Sync Master** es un gestor de sincronización inteligente que actúa como una capa de control profesional (wrapper) sobre motores de transferencia de datos como Rclone y clientes de nube. Permite automatizar el respaldo y la paridad de archivos entre directorios locales y servicios de nube (Google Drive, OneDrive, Mega, etc.) mediante una interfaz gráfica optimizada para el rendimiento y la transparencia de procesos.

---

# 2. Características principales
- Tema Dark Renovado: Esquema #1E1E1E / #2D2D2D con tipografía generosa. Widgets circulares con **puntas redondeadas (RoundCap)**, carril de fondo gris y orientación a las 12:00.
- Gramática Reactiva: El centro de los anillos cambia de **"Sincronizando"** (Azul) a **"Sincronizado"** (Verde) al finalizar con éxito.
- Dashboard Sincronizado: Los contadores de Archivos, Advertencias y Errores están **color-coded** (Verde, Naranja, Rojo) y alineados milimétricamente.
- **Montaje remoto**: botones "Montar"/"Desmontar" en cada tarjeta cloud para exponer el remote como unidad FUSE; desmontaje automático al salir.
- **Anillo clicable**: clic sobre el anillo pausa/reanuda la sincronización; al pasar el cursor se muestra la acción.
- **Contadores interactivos**: pulsar un contador abre un detalle filtrado por categoría (archivos completados con nombres, advertencias o errores), agrupado por servicio.
- **Estados en lenguaje cotidiano**: los tooltips de las tarjetas explican cada estado sin tecnicismos.
- **Tarjetas autocentradas**: con pocos servicios el bloque queda centrado.
- **Auto-ajuste de ritmo**: ante límites de API el servicio reduce su concurrencia progresivamente y se recupera solo.
- **Client ID propio**: usa tu propio Client ID/Secret en GDrive y OneDrive con reconexión automática.
- **Exclusiones por proveedor**: presets de exclusión por defecto y adicionales para cada proveedor.
- Exclusiones Globales: Autogeneración de filtros en `~/.config/syncmaster/rclone_filters.txt` y silenciado automático de enlaces simbólicos mediante `--skip-links`.
- Guardias Rclone para la nube: `--transfers 2`, `--checkers 4`, `--tpslimit 5`, y `--drive-chunk-size 64M`.

---

# 3. Modos de uso
## A. Sincronización periódica: 
Cada servicio configura su intervalo (minutos). Los servicios locales (incluyendo Rclone) lanzan automáticamente el proceso según ese cron. El botón `Sincronizar servicios` fuerza manualmente ese lanzamiento para todos los servicios activos que no estén pausados ni deshabilitados.
## B. Pausar/Reanudar: 
Cada tarjeta tiene el botón `Pausar`/`Reanudar`. En pausa se vuelve amarillo y el texto cambia. Mientras está pausado no se ejecutan cron ni sincronizaciones manuales.
## C. Modo Standby del log:
La consola muestra un placeholder con `[Servicio] En ejecución....` hasta que llega un mensaje considerado relevante. Los mensajes ignoran los ruidos en JSON y `Building path`.
## D. Gestión de caché Rclone:
El diálogo permite elegir servicios específicos (Local, GDrive, OneDrive y Mega-Dev). Tras limpiar la caché se pregunta si resincronizar; si se responde “No”, se coloca `--resync` automáticamente para la próxima ejecución.

---

# 4. Interfaz Principal: Monitor en Tiempo Real
La pantalla principal ofrece una visión panorámica de la salud de tus datos.

### Reactividad en vivo
Cada servicio lanza un `ProcessWorker` en `QThread` con `--progress`, `--stats 1s`, `--stats-one-line` y `--use-json-log`. Esto garantiza que los arcos de progreso se vean al 100% de color incluso antes del primer porcentaje numérico y que el texto central evolucione gramaticalmente cada segundo.

## A. Tarjetas de Servicio
Cada servicio configurado se presenta en una tarjeta que contiene:

* **Estado:** Indica visualmente si el servicio está "Activo" (Verde), "Sincronizando" (Ámbar), "En Espera" (Amarillo) o "Limitado (API)" (Naranja).
* **Modo:** Muestra la lógica de transferencia seleccionada (Bisync ↔, Sync ↓, o Copy ↑).
* **Intervalo:** Tiempo programado entre ciclos automáticos.
* **Última Sinc:** Marca de tiempo exacta de la última actividad exitosa.
* **Botón Pausar/Reanudar (servicio local):** Permite detener o activar un servicio local de forma individual.
* **Botón Montar/Desmontar (servicios cloud):** Exponer el remote como punto de montaje FUSE o quitarlo; su estado se refleja en color y texto.
* **Anillo de progreso clicable:** Un clic pausa o reanuda la sincronización automática del servicio.

## B. Registro de Actividad y Errores
Consola técnica que filtra el ruido innecesario para mostrar solo:
* **Transferencias:** Archivos subidos/descargados con velocidad y tiempo estimado (ETA).
* **Avisos (NOTICE):** Información relevante sobre el estado de las sumas de comprobación o configuraciones del motor.
* **Errores Críticos:** Resaltados para una identificación inmediata.

## C. Barra de Controles Inferior
* **Limpiar Consola:** Vacía el registro de actividad para mejorar la legibilidad.
* **Limpiar Caché RClone:** Despliega un menú para borrar archivos de bloqueo (.lck) y metadatos corruptos, permitiendo re-sincronizar servicios trabados.
* **Sincronizar servicios:** Fuerza una ejecución inmediata de todos los servicios activos fuera de su horario programado.
* **Info:** Ventana con la versión, autoría de FerDev y detalles de la licencia de evaluación.
* **Configuración:** Acceso al panel de gestión técnica.
* **Salir:** Cierra la aplicación de forma segura.

---

# 5. Configuración y Personalización
El panel de configuración ahora se organiza en tres pestañas principales:

## A. Servicios
La pestaña `Servicios` funciona como un selector vertical. Al elegir un servicio, su tarjeta de configuración se muestra en el panel derecho.

Cada servicio permite configurar:
* **Habilitar:** Activa o desactiva el ciclo sin borrar datos.
* **Directorio Local/Remoto:** Define las rutas de origen y destino.
* **Intervalo:** Ajuste de la frecuencia de sincronización en minutos.
* **Exclusiones:** Un patrón por línea para omitir archivos o rutas.
* **Modo de Sincronización:** Selección entre bisync, sync o copy.

### Exclusiones: cómo escribirlas correctamente
Las exclusiones se escriben en el campo `Exclusiones` de cada servicio y se interpretan de forma independiente por servicio. La regla general es simple: escribe un patrón por línea y usa rutas o nombres relativos al directorio que sincroniza ese servicio, no rutas absolutas del sistema.

Para servicios basados en Rclone:
* Cada línea se convierte en una regla `--exclude`.
* El patrón se evalúa contra la ruta que el servicio está sincronizando.
* Si el servicio sincroniza `/home/usuario/DEV`, entonces `papirus-icon-theme/**` excluye `/home/usuario/DEV/papirus-icon-theme`.

Ejemplos útiles para Rclone:
```text
*.tmp
*.bak
node_modules/**
cache/**
papirus-icon-theme/**
```

Ejemplos más precisos:
```text
target/**
__pycache__/**
.git/**
.DS_Store
```

Para servicios `bisync`, `sync` o `copy` basados en Rclone, estas exclusiones afectan el contenido que se reporta al motor. Si el patrón no coincide con la ruta relativa correcta, el archivo o carpeta seguirá sincronizándose.

Para OneDrive:
* La app traduce el texto de exclusiones a `skip_file` y `skip_dir` en la configuración del cliente.
* Recomendable usar patrones simples y consistentes, por ejemplo `*.tmp`, `node_modules/` o `~*`.
* Si agregas una carpeta completa, usa tanto el nombre de la carpeta como su contenido, por ejemplo:
```text
MiCarpeta/
MiCarpeta/**
```

Buenas prácticas:
* Evita rutas absolutas como `/home/usuario/...` dentro del campo de exclusiones.
* Usa patrones relativos al punto que sincroniza el servicio.
* Mantén una exclusión por línea para que la app la procese de forma limpia.
* Verifica el nombre exacto de la carpeta, incluyendo mayúsculas y minúsculas si tu sistema las distingue.

## B. Agregar Servicios
Desde esta pestaña puedes:
* **Servicios RClone:** Mantiene el flujo actual para crear proveedores de nube (con exclusiones por proveedor preconfiguradas).
* **Servicio Local:** Permite crear un nuevo servicio local con la misma lógica del servicio local principal.

## C. Client ID propio (Google Drive / OneDrive)
En los formularios de GDrive, OneDrive y servicios Rclone encontrarás el botón **"Usar tu propio Client ID (reconectar)"**:
1. Pega tu Client ID y Client Secret de la consola del proveedor.
2. La app los aplica con `rclone config update --all`.
3. Se abre la terminal interactiva de `rclone config reconnect` para volver a autenticar.
4. Al terminar, el servicio queda reconectado con tu Client ID.

## D. General
* **Inicio Automático:** Opción para que la aplicación arranque con el sistema operativo y se mantenga en la bandeja de notificaciones.

---

# 6. Funciones de Guardia y Seguridad
* **API Guardian + Ritmo adaptativo:** Si se detecta "Quota Exceeded", "Error 429" o "rate limit exceeded", la app entra en modo "Limitado (API)" y reduce progresivamente el ritmo de transferencia (2/4/5 → 1/2/3 → 1/1/1), reintentando en 2 minutos; el nivel se persiste en `config.json`.
* **Connectivity Guard:** Verifica la conexión a los servidores de Microsoft o Google antes de iniciar, evitando intentos fallidos sin internet.
* **Auto-Sanación:** Detección automática de duplicados (dedupe) y limpieza de archivos de bloqueo huérfanos.
* **Client ID propio:** Reconexión con tu propio Client ID/Secret en GDrive y OneDrive.

---

# 7. Requisitos del Sistema
Para garantizar el funcionamiento óptimo de Sync Master v1.9.0, el entorno debe cumplir con:

* **Sistema Operativo:** Linux (Optimizado para Zorin OS y distribuciones basadas en Ubuntu/Debian).
* **Arquitectura:** x86_64 (paquete `.deb`).
* **Dependencias:** `python3 >= 3.10`, `python3-pyqt6` y motor `rclone >= 1.65` (se instalan automáticamente con el `.deb`).
* **Interfaz:** Entorno gráfico con soporte para temas oscuros (GTK/GNOME).
* **Conectividad:** Acceso a internet para la validación de tokens de API y transferencia de datos.

> **Versiones:** Este manual describe la distribución propietaria Sync Master v1.9.0, que incorpora montaje remoto, anillo clicable, contadores interactivos con desglose, auto-ajuste de ritmo ante cuota, asistente de Client ID propio y tarjetas autocentradas.

---

# 8. Documentación y licencia de evaluación privada
La entrega privada incluye `COPYRIGHT.txt`, `TERMS.md`, `FAQ.md` y este `USERGUIDE.md`. El software se distribuye bajo una Licencia de Evaluación Privada / Propietaria de FerDev, que mantiene todos los derechos reservados y prohíbe redistribuciones no autorizadas. Aquí se explica cómo Python actúa como wrapper propietario sobre Rclone y cómo se mantiene el control de estados en la UI cerrada.
