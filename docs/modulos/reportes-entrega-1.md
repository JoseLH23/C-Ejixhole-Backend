# Módulo Reportes — Entrega 1 de N (Financieros)

Ver `docs/modulos/reportes-diseno.md` para el diseño completo aprobado
(12 endpoints + dashboard). Este documento cubre solo lo implementado
**en esta entrega**.

## Implementado en esta entrega

| Método | Ruta | Estado |
|---|---|---|
| GET | `/reportes/ingresos` | ✅ Completo y probado |
| GET | `/reportes/cuentas-por-cobrar` | ✅ Completo y probado |

**NO implementado todavía** (10 endpoints restantes del diseño +
`/reportes/dashboard`) — se agregan en próximas iteraciones sobre el
mismo `router` ya creado en `app/routes/reporte_routes.py`.

Todas las rutas de Reportes exigen rol `admin` (decisión ya aprobada).

## `GET /reportes/ingresos`

**Filtros:** `periodo` (`hoy`/`semana`/`mes`/`anio`, atajo) **o**
`desde`/`hasta` manuales, `agrupar_por` (`dia`/`semana`/`mes`, default
`dia`), `metodo_pago`, `servicio_id`.

Si no se manda ni `periodo` ni `desde`/`hasta`, el default es el mes
actual completo.

**Respuesta:** totales (`total_ingresos`, `total_reembolsos`,
`total_neto`), `num_pagos`, y `serie` — una lista de buckets por
periodo con ingresos/reembolsos/neto de cada uno.

Los reembolsos se restan del neto pero se reportan también por
separado, para que el admin vea ambos números.

## `GET /reportes/cuentas-por-cobrar`

**Filtro:** `antiguedad_minima_dias` (opcional) — solo reservaciones
con saldo pendiente de al menos esa antigüedad.

**Respuesta:** `total_pendiente`, `num_reservaciones`, y `items`
(una fila por reservación activa con saldo > 0, ordenadas por
antigüedad descendente — las más viejas primero, para priorizar
cobranza).

Solo considera reservaciones `pendiente`/`confirmada` — una cancelada
con saldo nunca cuenta como cuenta por cobrar real.

## Decisiones de implementación

- **Agrupación por periodo ocurre en Python**, no en SQL — tal como
  se decidió en el diseño (sección 1 de `reportes-diseno.md`), para
  evitar diferencias de comportamiento entre SQLite (tests) y
  Postgres (producción) al agrupar por fecha.
- **`ReporteRepository` solo filtra por dimensiones sin fecha**
  (`metodo_pago`, `servicio_id`) en SQL; el filtro de rango de fechas
  se aplica en el Service, en Python, sobre los resultados ya traídos.
- **Antigüedad de cuentas por cobrar** se mide desde
  `reservaciones.fecha_creacion`, no desde `fecha_visita` — representa
  hace cuánto existe la deuda, no cuándo es la visita.

## Cómo correr las pruebas

```bash
pytest tests/test_reportes.py -v
# Esperado: 19 passed

pytest tests/ -v
# Esperado: 97 passed (9+11+13+13+15+17+19)
```

## Cómo probarlo a mano

Los pagos de prueba en los tests usan fechas históricas insertadas
directo por ORM (la API no permite fijar `fecha_pago` manualmente, a
propósito). Para probar a mano con datos reales:

```bash
uvicorn app.main:app --reload
```

1. Login como admin.
2. Crea cliente, servicio, reservación, y registra un par de pagos
   (`POST /pagos`) en días distintos si quieres ver la serie agrupada.
3. `GET /reportes/ingresos?periodo=mes` → revisa el total y la serie.
4. Crea una reservación con pago parcial (anticipo menor al total).
5. `GET /reportes/cuentas-por-cobrar` → debe aparecer con su saldo.
