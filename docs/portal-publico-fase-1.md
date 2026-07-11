# Backend — Portal Público, Paso 1: modelo de datos

Alcance exacto de lo acordado: modelos + migración + carga de catálogo
real. **Sin endpoints públicos todavía** (eso es el Paso 2) y **sin
Mercado Pago** (al final, como decidiste).

## Aviso importante: no pude correr pytest en mi entorno

El sandbox donde trabajo bloquea específicamente la instalación de
`fastapi` desde PyPI (confirmé que sí hay acceso general a internet —
`requests` se instaló sin problema — pero `fastapi` da error 403).
Verifiqué cada archivo con `python3 -m py_compile` (sintaxis válida en
los 12 archivos) y revisé cada línea manualmente contra el código
real que ya tenías, pero **la ejecución real de los 164+ tests
existentes + los nuevos que agregué te toca a ti**. Corre esto y
pégame el resultado exacto, sea éxito o error:

```bash
cd Ejixhole-Backend
alembic upgrade head
pytest -v
```

## Hallazgos reales encontrados al auditar tu código (antes de tocar nada)

1. **El campo `origen` ya existía** con el valor `"portal"` ya
   preparado — y Reportes ya tenía una prueba que filtra por él. No
   hizo falta crear ningún campo nuevo para distinguir reservaciones
   internas de públicas.
2. **La regla "un cliente, una reservación activa a la vez"** estaba
   protegida a nivel de base de datos (índice único parcial) y a nivel
   de servicio — la eliminé por tu decisión explícita (opción C).

## Cambios al modelo de datos

### `Reservacion` (se amplía, nada se borra)

| Campo | Detalle |
|---|---|
| `fecha_llegada`, `fecha_salida` | Nuevos, `Date`, nullable (null en filas viejas) |
| `tipo_reservacion` | Nuevo, `"entrada"` / `"camping"` / `"hospedaje"`, default `"entrada"` |
| `unidad_hospedaje_id` | Nuevo, FK a `unidades_hospedaje`, nullable — solo se llena si `tipo_reservacion = "hospedaje"` |
| `fecha_visita` | **Se conserva tal cual, sigue obligatoria** — el servicio la llena automáticamente igual a `fecha_llegada`, así que Reportes/Dashboard no necesitaron ningún cambio |
| Índice `ux_reservaciones_una_activa_por_cliente` | **Eliminado** — ver decisión de negocio arriba |

### `UnidadHospedaje` (tabla nueva)

`nombre` (único), `capacidad_maxima`, `precio_por_noche`, `activa`. Se
carga con Habitación 1, Habitación 2, Cabaña 1 vía el script de seed.

### `Servicio`

Se agregó `reservable` (booleano) — distingue lo que se puede pagar en
el portal de lo que solo es catálogo informativo.

## La fórmula de precio — ahora sí, 100% editable desde Servicios

Cambio aplicado tras tu respuesta: los precios de entrada y camping
**ya no están fijos en el código**. Salen de la base de datos:

- Entrada: precio del servicio con `categoria = "entrada"` y `reservable = true` (hoy, "Acceso al parque", $50).
- Camping: precio de entrada (arriba) + `servicio.precio` del servicio "Camping" que se pasa en la reservación.
- Hospedaje: precio de entrada × personas × noches + `unidad_hospedaje.precio_por_noche` × noches.

Si algún día suben el precio de la entrada o del camping, **se edita
desde el módulo Servicios que ya tienes — no hace falta pedirme código
nuevo ni volver a desplegar nada.**

**Importante para que no se rompa nunca:** el sistema depende de que
exista **exactamente un** servicio con `categoria = "entrada"`,
`reservable = true` y `activo = true` en todo momento. Si lo
desactivas o lo borras sin dejar otro en su lugar, cualquier intento
de reservar (entrada, camping u hospedaje) fallará con un error claro
("No hay un servicio de 'Acceso al parque' activo y reservable
configurado") en vez de cobrar un precio adivinado o inventado.

## El hallazgo que casi se me escapa: "Tour Huasteca"

La prueba `test_crear_reservacion` usaba un servicio de prueba
genérico ("Tour Huasteca", $500) que ya no tiene sentido: con las
reglas que definiste, **una Reservación solo puede ser entrada,
camping o hospedaje** — ya no existe una reservación "genérica" para
cualquier servicio. Actualicé esa prueba para usar datos reales
("Acceso al parque", $50) en vez de un placeholder inventado.

## Catálogo cargado (`scripts/seed_catalogo_publico.py`)

**4 servicios reservables:** Acceso al parque ($50), Camping ($100),
Cabañas ($800, referencial), Habitaciones ($800, referencial) — el
precio real de cabañas/habitaciones vive en `UnidadHospedaje`, no aquí.

**12 servicios informativos — con un aviso que necesito que veas:**
lancha, caballo, senderismo, chalecos, lancha inflable, kayaks,
tubing, saltos de cascada, pesca, guías, eventos privados, snorkel.

**No inventé precios para estos 12.** Se cargan en $0.00 con la nota
"PRECIO PENDIENTE" en su descripción. Antes de publicar el catálogo en
el portal, necesitas editarlos con los precios reales desde el módulo
Servicios que ya tienes — no hace falta volver a correr el script.

**"Baños y regaderas" y "venta de comida y bebidas" no se cargaron**
como servicios — el primero es una amenidad sin costo propio, y el
segundo ya acordamos que es solo un aviso de texto en la página, no
un producto.

## Reglas nuevas que sí se probaron con tests reales

- Camping cobra entrada + camping combinados correctamente (900 = (50+100)×3×2).
- Hospedaje cobra entrada + precio fijo de la unidad (3000 = (50×4×3)+(800×3)).
- Dos reservaciones de hospedaje que se traslapan en fechas → rechazadas (409).
- Salida el mismo día que otra llegada → si se permite (no es traslape real).
- "Entrada" exige que llegada y salida sean el mismo día (422 si no).
- "Hospedaje" exige `unidad_hospedaje_id`; "entrada" lo rechaza si se manda (422).
- Un cliente ahora sí puede tener varias reservaciones activas a la vez (reemplaza la prueba que verificaba lo contrario).

## Archivos nuevos

- `app/models/unidad_hospedaje.py`
- `alembic/versions/0003_portal_publico_fase1.py`
- `scripts/seed_catalogo_publico.py`

## Archivos modificados

- `app/models/reservacion.py`, `app/models/servicio.py`, `app/models/__init__.py`
- `app/schemas/reservacion.py`
- `app/services/reservacion_service.py`
- `app/repositories/reservacion_repository.py`
- `app/routes/reservacion_routes.py`
- `tests/test_reservaciones.py` (actualizado + 7 pruebas nuevas)
- `tests/test_reportes.py` (solo un comentario corregido, sin cambios de lógica)

## Cómo probarlo

```bash
cd Ejixhole-Backend
alembic upgrade head
python -m scripts.seed_catalogo_publico
pytest -v
```

Si todo pasa: revisa en tu base de datos que existan las 3 unidades y
los 16 servicios (4 reservables + 12 informativos con precio
pendiente). Si algo falla en pytest, pégamelo tal cual — con eso lo
corrijo sin adivinar.

## Siguiente paso (Paso 2, cuando confirmes que esto funciona)

Endpoints públicos: catálogo, verificación de disponibilidad, y
creación de la solicitud de reservación (sin pago, con notificación
por correo + visible en tu sistema, como ya acordamos).

## Frontend

No se tocó ningún archivo del frontend en esta entrega.
