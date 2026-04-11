# Notas de versión - SyncMaster v1.6.5 (Worker Resiliente)

Sync Master v1.6.5 refuerza la persistencia de ejecución y documenta claramente la estabilidad conseguida durante las pruebas de estrés.

### Lo nuevo en v1.6.5:
- **Gestión segura del worker**: El `ProcessWorker` y los managers que dependen de él ahora llaman a `stop()` y `wait()` antes de recrear cualquier hilo; Qt ya no destruye los objetos en el hilo principal ni provoca cierres silenciosos tras largas sesiones.
- **Persistencia validada**: Dejamos la aplicación en modo minimizado durante horas y el log sólo registró líneas como `DEBUG: Detectado X% para...`, sin errores críticos ni cierres. El servicio permanece vivo incluso tras largos intervalos de sync continuos.
- **Monitor sin interrupciones**: El sistema de logging mantiene el filtro inteligente y el panel de estados muestra la actividad de OneDrive, Mega y los demás servicios sin perder registros cuando se dispara una sincronización manual.

### Recomendación:
Actualiza a esta versión para garantizar que tus tareas de sincronización no se interrumpan y que el dashboard refleje correctamente los ciclos en curso.
