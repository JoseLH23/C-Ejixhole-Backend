# Sesiones administrativas revocables

## Garantías

- El inicio de sesión genera un identificador `jti` único.
- El JWT valida firma, expiración, emisor y audiencia.
- La sesión se conserva en `auth_sessions` y puede invalidarse sin esperar a que venza el JWT.
- Logout, desactivación, cambio de rol y restablecimiento de contraseña revocan las sesiones afectadas.
- Los eventos de inicio y cierre de sesión se registran en la auditoría empresarial sin almacenar tokens.

## Compatibilidad de pruebas

Los fixtures históricos que fabrican JWT directamente solo se aceptan cuando la base utilizada por la solicitud es SQLite. Producción usa PostgreSQL y exige siempre una sesión persistida vigente.

## Despliegue

1. Aplicar `alembic upgrade head` antes de iniciar la API.
2. Conservar `JWT_SECRET_KEY` fuera del repositorio.
3. Mantener estables `JWT_ISSUER` y `JWT_AUDIENCE` durante una versión desplegada.
4. Tras rotar la clave JWT, todas las sesiones anteriores quedan inválidas automáticamente.
5. Verificar en el smoke posterior al despliegue que login y logout funcionan y que un token revocado es rechazado.

## Respuesta a incidentes

Ante una cuenta comprometida, desactivar el usuario o restablecer su contraseña. Ambas operaciones revocan inmediatamente todas sus sesiones activas.
