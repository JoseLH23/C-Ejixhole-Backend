# Flujo operativo de una visita

## Secuencia oficial

```text
Reservación pendiente
→ confirmación
→ apertura de caja (si habrá efectivo)
→ registro de pagos
→ check-in
→ pago del saldo pendiente
→ check-out
→ visita completada
```

## Estados

- `pendiente`: solicitud o reservación aún no confirmada.
- `confirmada`: reservación aceptada y lista para recibir al visitante.
- `en_curso`: el visitante ya realizó check-in.
- `completada`: se realizó check-out y el saldo quedó totalmente pagado.
- `cancelada`: reservación anulada.

`en_curso` y `completada` no pueden asignarse con el endpoint genérico de
cambio de estado. Deben usarse los endpoints operativos para conservar fecha y
usuario responsable.

## Check-in

`POST /reservaciones/{id}/check-in`

Requisitos:

- usuario con rol `admin` u `operador`;
- reservación en estado `confirmada`.

El sistema registra fecha, usuario y cambia el estado a `en_curso`.

## Check-out

`POST /reservaciones/{id}/check-out`

Requisitos:

- usuario con rol `admin` u `operador`;
- reservación en estado `en_curso`;
- saldo pendiente igual a cero.

El sistema registra fecha, usuario y cambia el estado a `completada`.

## Pagos y caja

Los pagos por tarjeta, transferencia u otro método se registran normalmente.

Los pagos y reembolsos en efectivo requieren una sesión de caja abierta para el
usuario autenticado. El pago y el movimiento se guardan en la misma transacción:

- pago en efectivo → movimiento de ingreso;
- reembolso en efectivo → movimiento de egreso.

Si alguno falla, no se guarda ninguno. Esto evita dinero recibido que no aparezca
en el corte de caja.

## Compatibilidad

Las reservaciones completadas antes de la migración conservan una fecha
aproximada de check-in/check-out basada en su última actualización. Las
reservaciones activas en `en_curso` continúan bloqueando la unidad de hospedaje
contra traslapes.
