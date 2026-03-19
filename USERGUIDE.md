# Manual de Usuario: Sync Master v1.5.6
**Desarrollado por Miguel Fernando Cárdenas Alvear (FerDev)** *Solución Propietaria de Sincronización de Alta Resiliencia.

---

# 1. Introducción

**Sync Master** es un gestor de sincronización inteligente que actúa como una capa de control profesional (wrapper) sobre motores de transferencia de datos como Rclone y clientes de nube. Permite automatizar el respaldo y la paridad de archivos entre directorios locales y servicios de nube (Google Drive, OneDrive, Mega, etc.) mediante una interfaz gráfica optimizada para el rendimiento y la transparencia de procesos.

---

# 2. Características principales
- Tema Dark con tipografía +1 pt en controles y +2 pt en la consola de logs, tarjetas gris pizarra (#2D2D2D) y fondo gris carbón (#1E1E1E). Botones con bordes finos, enfoque visible y estados dinámicos por servicio.
- Trifecta de modos por servicio (bisync/copy/sync). Cada servicio muestra un sello con iconos ↔, ↑ o ⇄ en su tarjeta y un descriptor del modo actual.
- Logs inteligentes que filtran metadatos ruidosos (Modtime, HashType, Building Path, etc.) y muestran sólo eventos relevantes (transferencias, notices, errores). Cuando no hay actividad visible aparece `[Servicio] En ejecución....`.
- Limpieza selectiva de caché Rclone con diálogo de casillas y opción de re-sincronizar o programar `--resync`.
- Protección a errores frecuentes: ignorar `cannot remove lockfile ... no such file or directory`, reintentos automáticos, y detección de `Quota exceeded` para pausar servicios 5 minutos y cambiar el estado a `Limitado (API)`.
- Guardias Rclone para la nube: `--transfers 2`, `--checkers 4`, `--tpslimit 5`, y `--drive-chunk-size 64M` cuando se sincroniza con Google Drive.

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
* **liminar Seleccionado:** Quita servicios de la lista de gestión.
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
Para garantizar el funcionamiento óptimo de Sync Master v1.5.6, el entorno debe cumplir con:

* **Sistema Operativo:** Linux (Optimizado para Zorin OS y distribuciones basadas en Ubuntu/Debian).
* **Arquitectura:** x86_64 para el paquete AppImage.
* **Dependencias:** Motor Rclone configurado y, para servicios específicos, el cliente de OneDrive.
* **Interfaz:** Entorno gráfico con soporte para temas oscuros (GTK/GNOME).
* **Conectividad:** Acceso a internet para la validación de tokens de API y transferencia de datos.

---

# 8. Documentación y licencia de evaluación privada
La entrega privada incluye `COPYRIGHT.txt`, `TERMS.md`, `FAQ.md` y este `USERGUIDE.md`. El software se distribuye bajo una Licencia de Evaluación Privada / Propietaria de FerDev, que mantiene todos los derechos reservados y prohíbe redistribuciones no autorizadas. Aquí se explica cómo Python actúa como wrapper propietario sobre Rclone y cómo se mantiene el control de estados en la UI cerrada.
