# Monitoreo y alertas de producción

## Objetivo

Detectar rápidamente si deja de responder alguna pieza pública de EjiXhole:

- backend en Render;
- conexión del backend con PostgreSQL;
- configuración de notificaciones por correo;
- portal público de reservaciones;
- panel administrativo.

## Endpoints de salud

### `GET /health/live`

Confirma únicamente que el proceso HTTP está vivo. No consulta la base de
datos y es apropiado para comprobaciones de liveness.

### `GET /health/ready`

Ejecuta `SELECT 1` en PostgreSQL y devuelve:

```json
{
  "status": "ready",
  "checks": {
    "database": "up",
    "notifications": "configured"
  }
}
```

Si PostgreSQL no responde, devuelve HTTP `503` sin exponer la excepción ni la
cadena de conexión.

La comprobación de notificaciones valida que exista una configuración completa
de Resend o SMTP. No envía correos sintéticos de forma periódica para evitar
spam y consumo innecesario.

## Monitor automático

El workflow `.github/workflows/production-monitor.yml` se ejecuta dos veces por
hora y también puede ejecutarse manualmente.

Cada ejecución:

1. consulta `/health/ready` del backend;
2. comprueba PostgreSQL y configuración de notificaciones;
3. comprueba que el portal entregue el contenedor React;
4. comprueba que el panel administrativo entregue el contenedor React;
5. reintenta para tolerar un arranque en frío de Render;
6. crea o actualiza un Issue de alerta si algo falla;
7. cierra el Issue automáticamente cuando todo se recupera.

Título del Issue automático:

```text
[ALERTA] Servicios de EjiXhole no disponibles
```

El fallo también deja la ejecución de GitHub Actions en rojo, por lo que las
notificaciones de Actions e Issues del repositorio deben permanecer activadas.

## URLs predeterminadas

- Backend: `https://c-ejixhole-backend.onrender.com/health/ready`
- Portal: `https://ejixhole-reservas.vercel.app/`
- Panel: `https://ejixhole-frontend.vercel.app/`

Pueden reemplazarse sin modificar código mediante variables del repositorio:

- `BACKEND_HEALTH_URL`
- `PORTAL_URL`
- `ADMIN_URL`

## Registro de errores críticos

Todas las respuestas HTTP incluyen `X-Request-ID`.

Los errores no controlados y respuestas `5xx` se registran con:

- identificador de petición;
- método HTTP;
- ruta;
- código de estado;
- duración.

No se registran cuerpos, tokens, contraseñas ni datos personales.

## Alcance y límites

Este monitor detecta indisponibilidad y configuración incompleta. No sustituye
una plataforma especializada de métricas, trazas o captura de excepciones.

El siguiente nivel operativo será conectar estos registros con un proveedor de
observabilidad cuando el volumen real lo justifique. La entrega real de correo
se sigue validando mediante el flujo end-to-end de reservación.
