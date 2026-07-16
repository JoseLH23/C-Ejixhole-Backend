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

## Estado actual

Esta entrega crea y prueba la bandeja de salida. Los eventos permanecen con estado `pending`; todavía no se envían por red.

La siguiente entrega añadirá el publicador confiable hacia MH-Core con firma, reintentos, bloqueo concurrente, registro de respuestas y deduplicación en el consumidor.
