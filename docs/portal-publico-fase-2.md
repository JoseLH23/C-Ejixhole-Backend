# Backend — Portal Público, Paso 2: endpoints públicos

Alcance exacto de lo acordado: catálogo, disponibilidad, creación de
solicitud de reservación **sin pago** (llega en la próxima fase), con
notificación por correo (opcional, degradable) + siempre visible en tu
sistema interno de inmediato.

## Hallazgos de la auditoría (antes de escribir código)

1. **`usuario_id` era obligatorio** en `Reservacion`, pero una reservación pública no la crea ningún empleado. Confirmé que no se usa en ningún Reporte — se volvió opcional sin riesgo.
2. **El CORS solo permite `localhost:5173`** (tu frontend interno). Cuando construyamos el sitio público (Paso 3, otro puerto/dominio), habrá que agregar su origen aquí. No bloquea este paso — hoy se prueba directo contra la API.
3. **Corrección retroactiva necesaria:** el script de seed que ya corriste dejó "Camping" con `categoria="hospedaje"` (código viejo). Agregué `scripts/fix_categoria_camping.py` — corre eso una vez para arreglarlo en tu base real (no genera error si ya está bien).

## Los 4 endpoints nuevos (todos sin autenticación — únicos así en todo el backend)

| Endpoint | Qué hace |
|---|---|
| `GET /publico/servicios` | Las 12 actividades informativas (nombre, descripción, precio) |
| `GET /publico/unidades-hospedaje` | Habitación 1, Habitación 2, Cabaña 1 (para que el visitante elija) |
| `GET /publico/disponibilidad` | `{disponible: true/false}` para una unidad + rango de fechas |
| `POST /publico/reservaciones` | Crea la solicitud — siempre queda en estado "pendiente" |

**El visitante nunca manda un `servicio_id`** — no le corresponde conocer ese detalle interno. El sistema lo resuelve solo, según `tipo_reservacion` y (si aplica) qué unidad eligió.

## Cliente: se reutiliza, no se duplica

A diferencia del flujo interno (`ClienteService.crear()`, que SIEMPRE crea un cliente nuevo y solo avisa de duplicados para que recepción decida), el portal público **busca primero por teléfono o email** y reutiliza el cliente si ya existe — un visitante que reserva varias veces no genera un registro repetido cada vez. Confirmado con una prueba real (`test_crear_solicitud_reutiliza_cliente_existente`).

## El correo: construido pero "apagado" hasta que me des credenciales

`app/services/notificacion_service.py` está listo para enviar correos reales por SMTP, pero **si no configuras `SMTP_HOST`/`SMTP_USER`/`SMTP_PASSWORD`/`NOTIFICACIONES_EMAIL_DESTINO` en tu `.env`, el sistema sigue funcionando exactamente igual** — la reservación se crea y aparece en tu Dashboard de inmediato, solo no se manda el correo (se registra en el log). Nunca un problema de correo puede tumbar la creación de una reservación real.

Cuando tengas una cuenta de correo lista (Gmail funciona, usando una "contraseña de aplicación", no tu contraseña normal), agrega esos 4 valores a tu `.env` y el correo empieza a enviarse sin tocar código.

## Archivos nuevos

- `app/routes/publico_routes.py`
- `app/services/publico_service.py`
- `app/services/notificacion_service.py`
- `app/schemas/publico.py`
- `alembic/versions/0004_usuario_id_opcional.py`
- `scripts/fix_categoria_camping.py`
- `tests/test_publico.py` (11 pruebas nuevas)

## Archivos modificados

- `app/models/reservacion.py` (`usuario_id` ahora opcional)
- `app/schemas/reservacion.py` (`ReservacionOut.usuario_id` ahora opcional)
- `app/services/reservacion_service.py` (acepta `usuario_id=None`)
- `app/core/config.py` y `.env.example` (settings de SMTP, todos opcionales)
- `app/main.py` (registra el router público)
- `scripts/seed_catalogo_publico.py` (categoria de "Camping" corregida a `"camping"`)

## Cómo probarlo

```bash
cd Ejixhole-Backend
alembic upgrade head
python -m scripts.fix_categoria_camping
pytest -v
```

Deberías ver **171 + 11 = 182 passed**. Si algo falla, pégamelo tal cual.

Después, prueba los endpoints manualmente (con la API corriendo):

```bash
curl http://localhost:8000/publico/servicios
curl http://localhost:8000/publico/unidades-hospedaje
curl "http://localhost:8000/publico/disponibilidad?unidad_hospedaje_id=1&fecha_llegada=2026-08-15&fecha_salida=2026-08-18"
```

Y confirma en tu sistema interno (módulo Reservaciones) que cualquier solicitud que crees vía `POST /publico/reservaciones` aparece ahí de inmediato, en estado "pendiente".

## Siguiente paso (Paso 3, cuando confirmes que esto funciona)

El sitio web público — lo que realmente ve y usa el visitante. Ahí es
donde se resuelve el tema de CORS (agregar el origen del sitio nuevo).

## Frontend interno

No se tocó ningún archivo del frontend interno (Experience OS) en esta entrega.
