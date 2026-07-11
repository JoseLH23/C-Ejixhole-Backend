# Reportes — Mini-entrega: huecos para Dashboard

Cubre las 3 decisiones aprobadas en `dashboard-diseno.md` antes de
tocar el Dashboard en sí.

## 1. `GET /reportes/clientes-nuevos`

**Filtros:** `periodo`/`desde`/`hasta`, `agrupar_por` (`dia`/`semana`/`mes` — **no** admite `metodo_pago`, no aplica aquí).
**Entrega:** `total` + `serie` (clientes nuevos por bucket de fecha).
Cuenta por `Cliente.fecha_creacion`.

## 2. `GET /reportes/proximas-reservaciones`

**Filtros:** `dias` (default 7), `estado` (default `"confirmada"` — la
tarjeta del Dashboard pidió específicamente confirmadas, pero se puede
pedir cualquier otro estado, o mandar `estado=null`... nota: por ahora
un solo valor a la vez, no una lista).
**Entrega:** `total` + `items` (una fila por reservación, con nombre
de cliente y servicio ya resueltos, ordenadas por `fecha_visita`
ascendente — la más próxima primero).

## 3. `GET /reportes/ingresos?agrupar_por=metodo_pago`

Se extendió el endpoint que ya existía — **no es una ruta nueva**.
`agrupar_por` ahora acepta `metodo_pago` además de `dia`/`semana`/`mes`.
Cuando se usa, el campo `periodo` de cada item de la serie contiene el
método de pago (`"efectivo"`, `"tarjeta"`, etc.) en vez de una fecha —
se reutiliza el mismo campo para no romper el contrato de respuesta
existente ni crear un schema paralelo.

## Bug que encontré y corregí en mí mismo, antes de entregarlo

Al separar la validación de `agrupar_por` en dos constantes
(`AGRUPACIONES_FECHA` para tendencia/clientes-nuevos,
`AGRUPACIONES_INGRESOS` para ingresos), accidentalmente borré las dos
líneas que resuelven el rango de fechas y traen los pagos dentro de
`reporte_ingresos`. Lo detecté revisando el archivo completo antes de
escribir los tests — quedó corregido y verificado que la lógica
correcta sigue intacta.

## Cómo correr las pruebas

```bash
pytest tests/test_reportes.py -v
# Esperado: 61 passed (45 anteriores + 16 nuevas)

pytest tests/ -v
# Esperado: 139 passed
```

## Siguiente paso

Con estos 3 huecos cubiertos y probados, Dashboard ya puede
implementarse sin necesitar ningún cálculo propio — todo lo que
`dashboard-diseno.md` pedía ya existe en Reportes.
