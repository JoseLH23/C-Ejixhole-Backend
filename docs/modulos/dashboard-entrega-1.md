# Dashboard API — Entrega 1: `/dashboard/resumen`

Ver `docs/modulos/dashboard-diseno.md` para el diseño completo
aprobado. Este documento cubre solo lo implementado en esta entrega.

## Endpoint

`GET /dashboard/resumen` — rol `admin` únicamente.

Devuelve `{"fecha": "...", "tarjetas": [...]}` con las 9 tarjetas de
la pantalla principal, cada una con esta forma:

```json
{
  "titulo": "Ingresos hoy",
  "valor": "300.00",
  "comparacion_valor_anterior": "100.00",
  "comparacion_porcentaje": 200.0,
  "tendencia": "up"
}
```

Las tarjetas sin comparación definida (Reservaciones activas, Próximas
7 días, Saldo pendiente, Ocupación promedio, Diferencia de caja) traen
`comparacion_valor_anterior`, `comparacion_porcentaje` y `tendencia`
en `null` — no se inventó una comparación que el diseño no pidió.

## Arquitectura: sin Repository propio

`DashboardService` no tiene `DashboardRepository` — no toca la base de
datos directamente. Todo el dato sale de `ReporteService` y
`CajaService`, ya existentes. La única "agregación" que hace
Dashboard por su cuenta es sumar `sesion.diferencia` de las sesiones
que ya trae `CajaService.obtener_corte_dia()` — ese campo ya lo
calculó `CajaService.cerrar_sesion()`, aquí solo se suma.

## De dónde sale cada tarjeta

| Tarjeta | Fuente | Comparación vs. |
|---|---|---|
| Ingresos hoy | `reporte_ingresos(periodo="hoy")` | Ayer |
| Ingresos del mes | `reporte_ingresos(periodo="mes")` | Mes anterior |
| Reservaciones activas | `reporte_reservaciones_por_estado(periodo="anio")` | — |
| Próximas 7 días | `reporte_proximas_reservaciones(dias=7)` | — |
| Saldo pendiente total | `reporte_cuentas_por_cobrar()` | — |
| Tasa de cancelación (mes) | `reporte_cancelaciones(periodo="mes")` | Mes anterior |
| Ocupación promedio (mes) | `reporte_ocupacion(periodo="mes")`, promedio de los `porcentaje_ocupacion_promedio` de todos los servicios | — |
| Diferencia de caja (hoy) | `CajaService.obtener_corte_dia()`, suma de `diferencia` | — |
| Clientes nuevos (mes) | `reporte_clientes_nuevos(periodo="mes")` | Mes anterior |

## Limitación conocida, documentada a propósito: "Reservaciones activas"

No existe (todavía) un reporte que cuente "reservaciones activas ahora
mismo, sin importar cuándo se crearon". `reporte_reservaciones_por_estado`
siempre filtra por `fecha_creacion` dentro de un rango. Se usó
`periodo="anio"` (todo el año actual) como la mejor aproximación
disponible sin inventar una query nueva fuera de Reportes.

**Esto es correcto para un sistema que no lleva más de un año
operando** (que es el caso de EjiXhole ahora). Si en el futuro una
reservación de un año calendario anterior sigue sin completarse o
cancelarse, este número la subestimaría. Si eso llega a importar,
la solución correcta es agregar un método a `ReporteRepository`
específico para esto (ej. `obtener_reservaciones_activas_totales`,
similar a lo que ya existe para cuentas por cobrar) — no vale la pena
adelantarlo ahora sin evidencia de que se necesita.

## Cómo correr las pruebas

```bash
pytest tests/test_dashboard.py -v
# Esperado: 13 passed

pytest tests/ -v
# Esperado: 152 passed
```

Las pruebas de comparación (hoy/ayer, mes/mes anterior) calculan las
fechas dinámicamente con `datetime.now()`, igual que en
`test_reportes.py` — no hay fechas fijas hardcodeadas, así que siguen
siendo válidas sin importar cuándo se ejecuten.

## Cómo probarlo a mano

```bash
uvicorn app.main:app --reload
```

1. Login como admin.
2. `GET /dashboard/resumen` con la base recién creada → todas las
   tarjetas deben venir en 0/null, sin error.
3. Crea algunos clientes, servicios, reservaciones y pagos.
4. Repite `GET /dashboard/resumen` → los números deben reflejar lo
   que acabas de crear.

## Pendiente (entregas futuras, mismo router `/dashboard`)

`/dashboard/ingresos`, `/reservaciones`, `/ocupacion`, `/servicios`,
`/clientes`, `/caja`, `/alertas` — no implementados todavía.
