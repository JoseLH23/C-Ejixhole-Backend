# Módulo Pagos — Completo

## Endpoints

| Método | Ruta                                  | Descripción |
|--------|----------------------------------------|-------------|
| POST   | `/pagos`                               | Registrar un pago (anticipo, pago_completo, pago_saldo o reembolso). |
| GET    | `/pagos`                               | Listar con filtros: `reservacion_id`, `tipo`, `metodo_pago`, `limit`, `offset`. |
| GET    | `/pagos/{id}`                          | Obtener un pago por id. 404 si no existe. |
| GET    | `/pagos/reservacion/{reservacion_id}`  | Historial de pagos de una reservación, en orden cronológico. |

## Reglas de negocio implementadas

1. **`monto_pagado` de la reservación se actualiza automáticamente** al registrar cada pago (sumando, o restando si es `reembolso`).
2. **Auto-confirmación**: si `monto_pagado >= total` y la reservación estaba `pendiente`, pasa a `confirmada` sola.
3. **No se puede pagar más del saldo pendiente** (pagos normales) — rechazado con 400.
4. **No se puede reembolsar más de lo que se ha pagado** — rechazado con 400.
5. **No se pueden registrar pagos nuevos sobre una reservación cancelada** — excepto reembolsos (si canceló con anticipo ya pagado, debe poder devolverse).

## Cómo correr las pruebas

```bash
pytest tests/test_pagos.py -v
```

Esperado: **14 passed**. SQLite en memoria, no toca tu Postgres real.

## Cómo probarlo a mano

```bash
uvicorn app.main:app --reload
```

Flujo sugerido en `http://localhost:8000/docs`:
1. Crea una reservación (módulo Reservaciones) y anota su `id` y `total`.
2. `POST /pagos` con `tipo: "anticipo"` y un monto menor al total → reservación sigue `pendiente`.
3. `GET /reservaciones/{id}` → verifica que `monto_pagado` y `saldo_pendiente` cambiaron.
4. `POST /pagos` de nuevo hasta cubrir el total → `GET /reservaciones/{id}` debe mostrar `estado: "confirmada"`.
5. `GET /pagos/reservacion/{id}` → verifica el historial completo.

## Sin migración nueva

El modelo `Pago` ya estaba completo desde la Fase 1 — no se tocó.

## Compatibilidad

No se modificó ningún archivo de Clientes ni Reservaciones. Los tests
de ambos módulos siguen corriendo igual (`pytest tests/ -v` corre las
tres suites juntas sin conflicto, cada una con su propia base SQLite
en memoria aislada).
