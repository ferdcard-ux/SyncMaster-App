# Notas de Versión - SyncMaster v1.6.4 (Stability Hotfix)

Esta versión resuelve de manera definitiva el problema de los "cierres silenciosos" identificados mediante la telemetría de la v1.6.3.

### Lo nuevo en v1.6.4:
- **Blindaje de Ciclo de Vida de Trabajadores**: Se corrigió una excepción `RuntimeError` que ocurría al intentar sincronizar servicios mientras Qt todavía estaba liberando memoria de procesos anteriores.
- **Gestión Segura de Hilos**: Implementada desconexión de señales y manejo de excepciones en la destrucción de hilos, asegurando que el inicio de una nueva sincronización no colisione con el cierre de la anterior.
- **Estabilidad Incrementada**: Se eliminaron las condiciones de carrera (Race Conditions) que provocaban que la aplicación se cerrara abruptamente sin dejar rastro en los registros básicos.

### Recomendación:
Se recomienda a todos los usuarios actualizar a esta versión para garantizar una operación continua en segundo plano sin interrupciones.
🏁
