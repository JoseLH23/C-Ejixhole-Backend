# Módulo Clientes — Completo

## Endpoints

| Método | Ruta               | Descripción                              |
|--------|---------------------|-------------------------------------------|
| POST   | `/clientes`          | Crear cliente. Devuelve el cliente creado + lista de posibles duplicados detectados. |
| GET    | `/clientes`          | Listar clientes (por defecto solo activos). Query params: `solo_activos`, `limit`, `offset`. |
| GET    | `/clientes/{id}`     | Obtener un cliente por id. 404 si no existe. |
| PUT    | `/clientes/{id}`     | Actualizar campos (solo los enviados). 409 si el nuevo teléfono/email choca con otro cliente. |
| DELETE | `/clientes/{id}`     | Soft delete (`activo = False`). 409 si el cliente tiene una reservación activa. |

## Reglas de negocio implementadas

1. **Detección de duplicados** (teléfono o email coincidente): no bloquea, solo alerta.
   Aplica tanto al crear como al actualizar.
2. **Soft delete**: nunca se borra un cliente físicamente, para no perder el
   historial de reservaciones. Se bloquea si tiene una reservación activa.

## Decisión de arquitectura tomada en este módulo

El modelo original no tenía campo `activo`. Se agregó vía migración
`0002_cliente_activo.py` para soportar soft delete sin romper la
integridad referencial con `reservaciones`.

## Capas

`routes` → `services` (reglas de negocio) → `repositories` (acceso a datos) → `models`

Este es el patrón que se repetirá en Reservaciones y Pagos.

## Cómo correr las pruebas

```bash
pip install -r requirements.txt
pytest tests/test_clientes.py -v
```

Las pruebas usan SQLite en memoria, no tu Postgres real — corren
aisladas y rápido, sin necesitar la base de datos levantada.

## Cómo aplicar la migración nueva en tu Postgres real

```bash
alembic upgrade head
```

Esto agrega la columna `activo` a la tabla `clientes` existente
(todos los clientes actuales quedan `activo = true` por defecto).
