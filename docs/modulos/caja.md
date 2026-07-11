# Módulo Caja — Completo

## Endpoints

| Método | Ruta                          | Descripción |
|--------|--------------------------------|-------------|
| POST   | `/caja/abrir`                  | Abrir una sesión de caja. |
| GET    | `/caja`                        | Listar sesiones. Filtros: `usuario_id`, `estado`, `limit`, `offset`. |
| GET    | `/caja/corte-dia`               | Corte de caja del día (default: hoy en UTC). Filtro opcional `fecha`, `usuario_id`. |
| GET    | `/caja/{id}`                   | Obtener una sesión por id. |
| POST   | `/caja/{id}/movimientos`        | Registrar un ingreso o egreso. |
| GET    | `/caja/{id}/movimientos`        | Listar movimientos de una sesión, orden cronológico. |
| POST   | `/caja/{id}/cerrar`             | Cerrar la sesión, calculando el esperado y la diferencia. |

Todas protegidas con JWT (cualquier rol autenticado y activo).

## Reglas de negocio implementadas

1. **Una sesión abierta por usuario a la vez** — Service (mensaje claro) + índice único parcial de Postgres como red de seguridad, igual que en Reservaciones.
2. **Saldo se calcula automáticamente**: `saldo_actual = monto_apertura + ingresos - egresos` (propiedad Python en el modelo, mismo patrón que `Reservacion.saldo_pendiente`).
3. **No se pueden registrar movimientos en una caja cerrada.**
4. **No se puede cerrar una caja ya cerrada.**
5. **Al cerrar**: `monto_cierre_esperado = saldo_actual` en ese momento, `diferencia = monto_cierre_real - monto_cierre_esperado` (negativo = faltante, positivo = sobrante).
6. **Corte del día**: agrega todas las sesiones cuya `fecha_apertura` cae en la fecha pedida (día UTC), sumando ingresos/egresos de todos sus movimientos — incluye sesiones ya cerradas y abiertas ese día.

## Ajuste técnico en el modelo (sin migración nueva)

Mismo ajuste que se hizo en `Reservacion`: se agregó `sqlite_where` junto a `postgresql_where` en el índice único parcial de `caja_sesiones`. No cambia nada en tu Postgres real — solo hace que los tests con SQLite repliquen el mismo comportamiento parcial.

También se agregó la propiedad `saldo_actual` al modelo `CajaSesion` (necesaria para que el schema de salida la pueda exponer), mismo patrón que `saldo_pendiente` en `Reservacion`.

## Decisión de diseño: corte del día filtra en Python, no en SQL

Se decidió comparar `fecha_apertura.date() == fecha` en Python en vez de un filtro `WHERE fecha_apertura BETWEEN ...` en la base de datos. Comparar `DateTime(timezone=True)` por rango entre SQLite (tests) y Postgres (producción) puede comportarse distinto según cómo cada dialecto maneja el timezone en el binding — se prefirió la opción más simple y predecible dado que el volumen de sesiones de caja de un parque es bajo (no hay problema de rendimiento real).

## Fuera de alcance de este módulo (a propósito)

- Vincular automáticamente los pagos en efectivo (módulo Pagos) como movimientos de caja — el modelo ya soporta `CajaMovimiento.pago_id` nullable para esto, pero integrarlo modificaría `PagoService`, y la instrucción explícita fue no tocar Pagos en este módulo.
- Restricción por rol (ej. "solo cajero puede abrir caja") — no se definió esa regla, cualquier rol autenticado puede operar caja por ahora.

## Cómo correr las pruebas

```bash
pytest tests/test_caja.py -v
# Esperado: 17 passed

pytest tests/ -v
# Esperado: 78 passed (9+11+13+13+15+17)
```

## Cómo probarlo a mano

```bash
uvicorn app.main:app --reload
```

1. Login (`POST /auth/login`) → copia el token.
2. `POST /caja/abrir` con tu `usuario_id` y un `monto_apertura`.
3. Repite `POST /caja/abrir` para el mismo usuario → debe dar `409`.
4. `POST /caja/{id}/movimientos` con `tipo: "ingreso"` y otro con `"egreso"`.
5. `GET /caja/{id}` → verifica que `saldo_actual` refleja los movimientos.
6. `POST /caja/{id}/cerrar` con un `monto_cierre_real` distinto al esperado → revisa `diferencia`.
7. `GET /caja/corte-dia` → debe sumar todo lo del día.
