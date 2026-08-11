# Notas de versión - SyncMaster v1.9.0 (Montaje remoto y pulido)

Sync Master v1.9.0 añade el montaje remoto de servicios cloud, un anillo de progreso clicable y una fase de pulido completa del monitoreo y la resiliencia.

### Lo nuevo en v1.9.0:
- **Montaje remoto**: Botones "Montar"/"Desmontar" en cada tarjeta cloud para exponer el remote como unidad FUSE; desmontaje automático al cerrar la app.
- **Anillo de progreso clicable**: Pausa/reanuda la sincronización con un clic; el hover muestra la acción.
- **Contadores precisos**: "Archivos Completados" cuenta archivos reales transferidos (Copied/Updated/Moved/Renamed) desde el log; ya no depende del porcentaje del anillo.
- **Desglose por contador**: Al pulsar cada contador ves solo su categoría (archivos con nombres, advertencias o errores), agrupada por servicio.
- **Estados en lenguaje cotidiano** en los tooltips de las tarjetas.
- **Tooltips** en todos los controles activos.
- **Tarjetas autocentradas** con pocos servicios.
- **Auto-ajuste de ritmo**: ante límites de API (Quota exceeded, 429, rate limit) el servicio reduce su concurrencia progresivamente y se recupera solo.
- **Asistente de Client ID propio** para GDrive y OneDrive con reconexión automática.
- **Exclusiones por proveedor** preconfiguradas al crear servicios Rclone.
- **Filtro de ruido de estadísticas** para un monitor más limpio.

### Recomendación:
Actualiza a esta versión para aprovechar el montaje remoto, el control directo sobre cada servicio y el monitoreo interactivo con contadores precisos.
