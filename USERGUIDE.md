# Manual de Usuario: Sync Master v1.6.5
**Desarrollado por Miguel Fernando Cárdenas Alvear (FerDev)** Solución Propietaria de Sincronización de Alta Resiliencia.

---

# 1. Introducción

**Sync Master** es un gestor de sincronización inteligente que actúa como una capa de control profesional (wrapper) sobre motores de transferencia de datos como Rclone y clientes de nube. Permite automatizar el respaldo y la paridad de archivos entre directorios locales y servicios de nube (Google Drive, OneDrive, Mega, etc.) mediante una interfaz gráfica optimizada para el rendimiento y la transparencia de procesos.

---

# 2. Características principales
- Tema Dark Renovado: Esquema #1E1E1E / #2D2D2D con tipografía generosa. Widgets circulares con **puntas redondeadas (RoundCap)**, carril de fondo gris y orientación a las 12:00.
- Gramática Reactiva: El centro de los anillos cambia de **"Sincronizando"** (Azul) a **"Sincronizado"** (Verde) al finalizar con éxito.
- Dashnoard Sincronizado: Los contadores de Archivos, Advertencias y Errores están **color-coded** (Verde, Naranja, Rojo) y alineados milimétricamente.
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
* **Botón Pausar/Reanudar:** Permite detener o activar un servicio específico de forma individual.

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
El panel de configuración está dividido en pestañas para una gestión granular.

## A. Gestión de Servicios (Pestañas Individuales)
* **Habilitar [Nombre del Servicio]:** Casilla de verificación para activar o desactivar el ciclo de sincronización de ese servicio sin borrar sus datos.
* **Directorio Local/Remoto:** Define las rutas de origen y destino.
* **Intervalo:** Ajuste de la frecuencia de sincronización (en minutos).
* **Exclusiones:** Cuadro de texto para definir patrones de archivos que no deben sincronizarse (ej: target/**, __pycache__/**, *.tmp). Soporta comentarios con # para organizar tus reglas.
* **Modo de Sincronización:** Menú desplegable para elegir entre bisync, sync o copy.

## B. Servicios Rclone (Administración)
Desde esta pestaña puedes:
* **Añadir Servicio:** Inicia un asistente interactivo para configurar nuevos proveedores de nube.
* **Eliminar Seleccionado:** Quita servicios de la lista de gestión.
* **Tabla de Resumen:** Muestra el nombre, proveedor y ruta local de todos los servicios Rclone registrados.

## C. Pestaña General
* **Inicio Automático:** Opción para que la aplicación arranque con el sistema operativo y se mantenga en la bandeja de notificaciones.

---

# 6. Funciones de Guardia y Seguridad
* **API Guardian:** Si se detecta un error de "Quota Exceeded" en nubes como Google Drive, la app entra en modo "Limitado (API)" y pausa la actividad por 5 minutos para evitar bloqueos de cuenta.
* **Connectivity Guard:** Verifica la conexión a los servidores de Microsoft o Google antes de iniciar, evitando intentos fallidos sin internet.
* **Auto-Sanación:** Detección automática de duplicados (dedupe) y limpieza de archivos de bloqueo huérfanos.

---

# 7. Requisitos del Sistema
Para garantizar el funcionamiento óptimo de Sync Master v1.6.0, el entorno debe cumplir con:

* **Sistema Operativo:** Linux (Optimizado para Zorin OS y distribuciones basadas en Ubuntu/Debian).
* **Arquitectura:** x86_64 para el paquete AppImage.
* **Dependencias:** Motor Rclone configurado y, para servicios específicos, el cliente de OneDrive.
* **Interfaz:** Entorno gráfico con soporte para temas oscuros (GTK/GNOME).
* **Conectividad:** Acceso a internet para la validación de tokens de API y transferencia de datos.

> **Versiones:** Este manual describe la distribución propietaria Sync Master v1.6.5, que incluye el parche definitivo contra cierres silenciosos del worker en segundo plano.

---

# 8. Documentación y licencia de evaluación privada
La entrega privada incluye `COPYRIGHT.txt`, `TERMS.md`, `FAQ.md` y este `USERGUIDE.md`. El software se distribuye bajo una Licencia de Evaluación Privada / Propietaria de FerDev, que mantiene todos los derechos reservados y prohíbe redistribuciones no autorizadas. Aquí se explica cómo Python actúa como wrapper propietario sobre Rclone y cómo se mantiene el control de estados en la UI cerrada.
