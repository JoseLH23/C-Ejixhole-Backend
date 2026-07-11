# Módulo Servicios — Completo

## Endpoints

| Método | Ruta                  | Descripción |
|--------|------------------------|-------------|
| POST   | `/servicios`           | Crear servicio. |
| GET    | `/servicios`           | Listar. Query params: `solo_activos` (default `true`), `categoria`, `limit`, `offset`. |
| GET    | `/servicios/{id}`      | Obtener por id. 404 si no existe. |
| PUT    | `/servicios/{id}`      | Actualizar campos (solo los enviados). |
| DELETE | `/servicios/{id}`      | Soft delete (`activo = False`). |

## Reglas de negocio implementadas

1. **`precio` no negativo**, **`duracion_minutos`** y **`capacidad_maxima`** deben ser mayores a 0 si se envían — validado en el schema (Pydantic), antes de tocar la base de datos.
2. **No se puede desactivar un servicio con una reservación activa** (`pendiente`/`confirmada`) — mismo patrón que Clientes.
3. **No se puede reducir `capacidad_maxima` por debajo de una reservación activa ya existente** con más personas que la nueva capacidad — evita dejar reservaciones "imposibles" silenciosamente.

## Sin migración nueva

El modelo `Servicio` ya tenía el campo `activo` desde la Fase 1 (a diferencia de `Cliente`, que sí necesitó una migración). No se tocó el modelo.

## Compatibilidad verificada

Único archivo existente modificado: `app/main.py` (registro del router, 3 líneas). Clientes, Reservaciones y Pagos no se tocaron — confirmado con `git diff --stat` contra el commit estable.

## Cómo correr las pruebas

```bash
pytest tests/test_servicios.py -v
```

Esperado: **13 passed**. SQLite en memoria, no toca tu Postgres real.

```bash
pytest tests/ -v
```

Esperado: **46 passed** (9 clientes + 11 reservaciones + 13 pagos + 13 servicios).

## Cómo probarlo a mano

```bash
uvicorn app.main:app --reload
```

En `http://localhost:8000/docs`: crea un servicio con `POST /servicios`,
luego úsalo en `POST /reservaciones` (ya no hace falta insertarlo a mano
en pgAdmin como antes). Prueba `DELETE /servicios/{id}` sobre uno sin
reservaciones (debe funcionar) y sobre uno con una reservación activa
(debe dar 409).
