# Módulo Reportes — Entrega 2 (Operacionales)

Ver `docs/modulos/reportes-diseno.md` para el diseño completo, y
`docs/modulos/reportes-entrega-1.md` para los reportes financieros.

## Implementado en esta entrega

| Método | Ruta | Filtros |
|---|---|---|
| GET | `/reportes/ocupacion` | `periodo`/`desde`/`hasta`, `servicio_id` |
| GET | `/reportes/servicios-mas-vendidos` | `periodo`/`desde`/`hasta`, `limit` (default 10) |
| GET | `/reportes/clientes-frecuentes` | `periodo`/`desde`/`hasta`, `limit`, `minimo_reservaciones` (default 2) |
| GET | `/reportes/reservaciones-por-estado` | `periodo`/`desde`/`hasta`, `servicio_id`, `origen` |
| GET | `/reportes/cancelaciones` | `periodo`/`desde`/`hasta` |
| GET | `/reportes/tendencia-reservaciones` | `periodo`/`desde`/`hasta`, `agrupar_por` (dia/semana/mes), `estado` |

Todas exigen rol `admin`, sobre el mismo router de `/reportes` ya
existente. **Sin `/reportes/dashboard`, sin gráficos, sin IA** — tal
como se pidió explícitamente para esta entrega.

## Decisiones de implementación importantes

### Ocupación: porcentaje PROMEDIO por reservación, no acumulado

`capacidad_maxima` de un `Servicio` es un límite **por reservación**
(ej. "máximo 10 personas por tour"), no una capacidad total del
periodo. Sumar todas las personas reservadas en un rango y dividir
entre `capacidad_maxima` no tendría un significado de negocio claro
(¿capacidad de qué, si el tour se repite muchas veces al día?).

Por eso `porcentaje_ocupacion_promedio` es el **promedio de
`num_personas / capacidad_maxima` entre todas las reservaciones** del
servicio en el rango — responde "en promedio, ¿qué tan llenas van las
reservaciones de este servicio?". Si el servicio no tiene
`capacidad_maxima` definida, el campo es `None` (no se inventa un
número sin base).

### "Vendido" excluye canceladas

`servicios-mas-vendidos` y `clientes-frecuentes` cuentan reservaciones
en estado `pendiente`, `confirmada` o `completada` — una cancelada no
representa una venta real que se concretó. `reservaciones-por-estado`
y `cancelaciones` sí cuentan las canceladas, porque ahí es
precisamente el foco del reporte.

### Antigüedad de fechas: `fecha_creacion`, no `fecha_visita`

Todos estos reportes (excepto `ocupacion`, que sí usa `fecha_visita`
porque mide ocupación de visitas) filtran por `fecha_creacion` —
representan cuándo se generó la actividad (la venta, la cancelación),
no cuándo es la visita futura.

### `clientes-frecuentes` y la regla de una reservación activa

Para que un cliente aparezca con 2+ reservaciones históricas sin violar
la regla de "una reservación activa a la vez", sus reservaciones
anteriores deben estar en un estado no activo (`completada` o
`cancelada`) — esto no es una limitación del reporte, es exactamente
cómo se comporta un cliente recurrente real: reservas pasadas ya
completadas, más quizás una nueva pendiente.

## Cómo correr las pruebas

```bash
pytest tests/test_reportes.py -v
# Esperado: 45 passed (19 de Entrega 1 + 26 de Entrega 2)

pytest tests/ -v
# Esperado: 123 passed
```

## Cómo probarlo a mano

```bash
uvicorn app.main:app --reload
```

1. Login como admin.
2. Crea un par de servicios y clientes, algunas reservaciones con
   distintos estados y `num_personas`.
3. `GET /reportes/ocupacion?periodo=mes` → revisa el promedio por servicio.
4. `GET /reportes/servicios-mas-vendidos` → ranking.
5. `GET /reportes/reservaciones-por-estado` → conteo por estado.
6. `GET /reportes/cancelaciones` → tasa y desglose.
7. `GET /reportes/tendencia-reservaciones?agrupar_por=semana` → serie de tiempo.
