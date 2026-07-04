# Módulo Reservaciones — Completo

## Endpoints

| Método | Ruta                              | Descripción |
|--------|-----------------------------------|-------------|
| POST   | `/reservaciones`                  | Crear reservación. Calcula `total = servicio.precio * num_personas`. |
| GET    | `/reservaciones`                  | Listar con filtros: `cliente_id`, `servicio_id`, `estado`, `fecha_desde`, `fecha_hasta`, `limit`, `offset`. |
| GET    | `/reservaciones/{id}`             | Obtener una reservación por id. 404 si no existe. |
| PATCH  | `/reservaciones/{id}/estado`      | Cambiar estado (`pendiente`→`confirmada`→`completada`, o →`cancelada`). |

## Nota temporal sobre `usuario_id`

El módulo Auth/Usuarios todavía no existe (no está en la lista de 3
módulos). Mientras tanto, `POST /reservaciones` pide `usuario_id`
explícito en el body. Cuando exista JWT, este campo se elimina del
schema y se toma del usuario autenticado — es un cambio de una línea
en `reservacion_routes.py` y `reservacion_service.py`.

## Reglas de negocio implementadas

1. **Una reservación activa por cliente**: bloqueado en dos capas —
   chequeo amigable en el Service (mensaje claro) y el índice único
   parcial de Postgres como red de seguridad real contra condiciones
   de carrera.
2. **Cliente debe estar activo** para poder reservar.
3. **Servicio debe estar activo** y respetar `capacidad_maxima` si está definida.
4. **Estados terminales** (`completada`, `cancelada`) no pueden cambiar de estado.
5. **Total se calcula automáticamente**: `precio del servicio × num_personas`.
   No se acepta un total manual desde la API — evita inconsistencias.

## Ajuste técnico en el modelo (sin migración nueva)

Se agregó `sqlite_where` junto a `postgresql_where` en el índice único
parcial de `reservaciones`. No cambia nada en tu Postgres real — solo
hace que las pruebas con SQLite en memoria repliquen el mismo
comportamiento parcial (sin esto, SQLite bloqueaba incorrectamente
casos válidos, como cliente con reservación cancelada + una nueva).

## Fuera de alcance de este módulo (a propósito)

- Editar fecha/num_personas de una reservación ya creada (recalcular
  total) — no se pidió, se propone antes de construirlo si lo necesitas.
- CRUD de Servicios — no está en tu lista de 3 módulos; los tests
  insertan un Servicio directo por ORM para poder probar Reservaciones.

## Cómo correr las pruebas

```bash
pytest tests/test_reservaciones.py -v
```

Esperado: **11 passed**. Usan SQLite en memoria — no tocan tu Postgres real.

## Cómo probarlo a mano

```bash
uvicorn app.main:app --reload
```

Abre `http://localhost:8000/docs`. Necesitas un `cliente_id` y
`servicio_id` reales de tu Postgres (usa `POST /clientes` para crear
un cliente; para un servicio, insértalo directo en pgAdmin ya que
todavía no tiene ruta propia) y un `usuario_id` (revisa la tabla
`usuarios` en pgAdmin, o inserta uno a mano si está vacía).

Flujo sugerido:
1. `POST /reservaciones` con esos ids → debe crear en estado `pendiente`.
2. Repite el mismo `POST /reservaciones` para el mismo cliente → debe dar `409`.
3. `PATCH /reservaciones/{id}/estado` con `{"nuevo_estado": "cancelada"}`.
4. Repite el `POST` original → ahora sí debe crear una nueva (la anterior ya no está activa).
