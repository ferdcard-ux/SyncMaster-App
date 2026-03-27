# Notas de Versión - SyncMaster v1.6.3 (Diagnostic Hotfix)

Esta versión es un parche de diagnóstico crítico diseñado para capturar la causa de los cierres silenciosos que no dejaban rastro en los registros anteriores.

### Lo nuevo en v1.6.3:
- **Redirección de Consola (Nuclear Logging)**: Todas las salidas del proceso (`stdout` y `stderr`) se redirigen ahora directamente a `crash.log`. Esto incluye fallos de bajo nivel de Qt o C++ que saltan fuera del manejador de excepciones de Python.
- **Forzado de Escritura (Flush)**: Cada mensaje escrito en el log se fuerza a disco inmediatamente. Esto garantiza que el log no quede vacío si el proceso es terminado abruptamente.
- **Modo Debug**: Se ha incrementado el nivel de detalle de los registros a `DEBUG` para una telemetría completa de la inicialización y el ciclo de vida de los servicios.
- **Gancho de Excepciones**: Se implementó `sys.excepthook` para capturar errores que ocurran fuera del bucle principal de eventos.

### Instrucciones para Diagnóstico:
Si la aplicación se cierra, por favor revisa el archivo en:
`~/.config/sync_master/crash.log`
🏁
