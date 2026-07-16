# Eventos de dominio y bandeja de salida

EjiXhole registra los cambios importantes del negocio en `outbox_events` dentro de la misma transacción PostgreSQL que modifica reservaciones, pagos o visitas.

## Eventos v1

- `reservation.created`
- `reservation.confirmed`
- `payment.recorded`
- `reservation.cancelled`
- `visit.completed`

Cada evento contiene:

- `id` UUID para deduplicación del consumidor;
- `event_key` único para no producir dos veces el mismo hito;
- tipo y versión de esquema;
- agregado e identificador relacionado;
- payload mínimo sin nombres, correos, teléfonos ni notas privadas;
- estado de entrega, intentos y próxima fecha disponible.

## Garantía transaccional

El evento no hace `commit` por separado. La operación de negocio agrega el evento a la misma sesión SQLAlchemy y confirma ambos juntos. Si el registro del evento falla, la reservación, pago, cancelación o salida también se revierte.

## Publicación hacia MH-Core

El proceso HTTP y el publicador son procesos separados. El worker se ejecuta con:

```powershell
python -m app.workers.outbox_publisher
```

Para procesar un solo lote y terminar:

```powershell
python -m app.workers.outbox_publisher --once
```

El publicador:

- reclama filas con `SELECT ... FOR UPDATE SKIP LOCKED`;
- marca cada evento como `processing` y asigna un lease por worker;
- recupera leases vencidos después de una caída;
- construye JSON canónico y firma `timestamp + "." + cuerpo` con HMAC SHA-256;
- valida que MH-Core confirme el contrato `v1` y el mismo `event_id`;
- considera un duplicado confirmado por MH-Core como entrega exitosa;
- reintenta errores de red, 408, 425, 429 y 5xx con backoff exponencial;
- envía errores permanentes o eventos agotados a `dead_letter`;
- registra solo diagnósticos truncados, nunca la clave de firma ni datos personales.

Estados posibles:

- `pending`: aún no reclamado;
- `processing`: reservado por un worker;
- `failed`: reintento programado;
- `published`: confirmado por MH-Core;
- `dead_letter`: requiere revisión o reenvío manual.

## Variables

- `MH_CORE_EVENTS_URL`: URL completa de `POST /integrations/ejixhole/events`.
- `MH_CORE_EVENT_SIGNING_SECRET`: misma clave que `EJIXHOLE_EVENT_SIGNING_SECRET` en MH-Core.
- `OUTBOX_BATCH_SIZE`.
- `OUTBOX_MAX_ATTEMPTS`.
- `OUTBOX_LEASE_SECONDS`.
- `OUTBOX_INITIAL_BACKOFF_SECONDS`.
- `OUTBOX_MAX_BACKOFF_SECONDS`.
- `OUTBOX_REQUEST_TIMEOUT_SECONDS`.
- `OUTBOX_POLL_INTERVAL_SECONDS`.

En producción `MH_CORE_EVENTS_URL` debe usar HTTPS y el worker debe ejecutarse como proceso persistente independiente del servidor web.
