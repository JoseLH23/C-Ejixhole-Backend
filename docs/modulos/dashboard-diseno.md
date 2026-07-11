# Diseño de Arquitectura — Dashboard API
### EjiXhole Experience OS

---

## 0. Principio rector

**El Dashboard no calcula nada nuevo.** Es una capa de **composición y
formato** sobre `ReporteService` y `CajaService`, que ya existen y ya
están probados. `DashboardService` solo:
1. Llama a los métodos de reporte que ya existen (a veces más de una
   vez, con distintos rangos de fecha, para poder comparar periodos).
2. Compone los resultados en la forma que la UI necesita (tarjetas,
   series para gráficas, listas de alertas).
3. Calcula comparaciones simples entre dos resultados ya agregados
   (ej. % de cambio entre "ingresos de hoy" e "ingresos de ayer") —
   esto es composición, no una agregación nueva.

**Regla dura: si un número que el Dashboard necesita no lo produce ya
un método existente de `ReporteService`/`CajaService`, ese número se
agrega primero a Reportes — nunca se calcula ad-hoc dentro de
`DashboardService`.** Ver sección 4 para los dos casos donde esto
aplica ahora mismo.

---

## 1. Separación Reportes vs. Dashboard

| | Reportes | Dashboard |
|---|---|---|
| Público | Analistas / admin explorando datos | Pantalla principal, uso diario |
| Filtros | Muchos, detallados | Pocos o ninguno (vista curada) |
| Forma de la respuesta | Datos crudos/series | Tarjetas, alertas, series listas para graficar |
| Quién la llama | Un usuario interactuando con filtros | La app al cargar una pantalla |

El Dashboard es un **cliente interno** de Reportes, ni más ni menos.

---

## 2. Endpoints del Dashboard

| Método | Ruta | Qué entrega |
|---|---|---|
| GET | `/dashboard/resumen` | Las tarjetas de KPI de la pantalla principal (sección 5) |
| GET | `/dashboard/ingresos` | Serie de ingresos lista para graficar + comparación vs. periodo anterior |
| GET | `/dashboard/reservaciones` | Desglose por estado + tendencia, listo para graficar |
| GET | `/dashboard/ocupacion` | Ocupación por servicio, listo para graficar/tabla |
| GET | `/dashboard/servicios` | Top servicios vendidos, listo para tabla/gráfica |
| GET | `/dashboard/clientes` | Clientes frecuentes + nuevos (ver hueco, sección 4) |
| GET | `/dashboard/caja` | Estado de caja de hoy: sesiones abiertas, corte del día |
| GET | `/dashboard/alertas` | Lista de alertas activas (sección 9) |

Ocho endpoints. `/dashboard/resumen` es el único que la pantalla
principal llama al cargar; los demás son para cuando el usuario entra
a una sección específica (mismo patrón ya aprobado en el diseño de
Reportes).

---

## 3. Detalle de cada endpoint

### `GET /dashboard/resumen`
**Reutiliza:** todos los reportes financieros y operacionales, una
sola vez cada uno con `periodo=hoy` y/o `periodo=mes` según la
tarjeta.
**Entrega:** la lista de tarjetas de la sección 7, ya calculadas
(valor actual + comparación).
**Filtros:** ninguno — es una vista fija.

### `GET /dashboard/ingresos`
**Reutiliza:** `ReporteService.reporte_ingresos` — se llama dos veces
(periodo actual y periodo anterior equivalente) para calcular el %
de cambio.
**Entrega:** serie diaria del mes actual + total actual + total
anterior + % de cambio.
**Filtros:** `periodo` (default `mes`).

### `GET /dashboard/reservaciones`
**Reutiliza:** `reporte_reservaciones_por_estado` +
`reporte_tendencia_reservaciones`.
**Entrega:** conteo por estado (para un donut/barras) + serie de
tendencia (para una línea).
**Filtros:** `periodo` (default `mes`).

### `GET /dashboard/ocupacion`
**Reutiliza:** `reporte_ocupacion` tal cual, sin cambios — el
Dashboard solo lo re-expone bajo su propio prefijo para que el
frontend no tenga que saber que "vive" en Reportes.
**Filtros:** `periodo` (default `mes`).

### `GET /dashboard/servicios`
**Reutiliza:** `reporte_servicios_mas_vendidos` con `limit=5` fijo
(la tarjeta del Dashboard no necesita el top 10 completo, eso ya
existe en `/reportes/servicios-mas-vendidos` si el admin quiere más).

### `GET /dashboard/clientes`
**Reutiliza:** `reporte_clientes_frecuentes` con `limit=5`.
**Hueco pendiente:** "clientes nuevos del mes" — ver sección 4.

### `GET /dashboard/caja`
**Reutiliza:** `CajaService.obtener_corte_dia` + `CajaService.listar_sesiones(estado="abierta")`.
**Entrega:** corte del día + lista de qué usuarios tienen caja abierta
ahora mismo (útil para saber quién sigue operando).

### `GET /dashboard/alertas`
**Reutiliza:** `reporte_cuentas_por_cobrar`, `reporte_cancelaciones`,
`listar_sesiones` (para diferencias de caja recientes). Ver sección 9
para las reglas exactas de cada alerta.

---

## 4. Huecos reales que encontré (decisión pendiente antes de implementar)

### Hueco 1: "Clientes nuevos del mes"
Estaba en el diseño original de Reportes (sección 3.C) pero **nunca
se implementó** en Entrega 1 ni 2 — no hay ningún método que cuente
clientes por `fecha_creacion`. El Dashboard lo necesita para la
tarjeta "Clientes nuevos" (sección 7).

**Opciones:**
- (a) Agregar `GET /reportes/clientes-nuevos` como mini-entrega de
  Reportes antes de tocar Dashboard (mantiene la regla de "todo pasa
  por Reportes primero").
- (b) Que `DashboardService` cuente esto directamente (es una query
  de una sola línea: `Cliente.fecha_creacion` en rango) ya que no hay
  ningún reporte que "duplicar" — technically no rompe la regla
  porque no hay nada que reusar todavía.

Mi recomendación: (a), por consistencia — así queda disponible también
para quien use Reportes directamente, no solo el Dashboard.

### Hueco 2: Ingresos por método de pago (para un gráfico de pastel)
`reporte_ingresos` permite **filtrar** por un `metodo_pago` a la vez,
pero no **agrupar** por método de pago en una sola llamada. Si el
Dashboard quiere un pie chart "efectivo vs. tarjeta vs. transferencia",
hoy tocaría llamar el endpoint 4 veces (uno por método).

**Opciones:**
- (a) Agregar `agrupar_por=metodo_pago` como una opción más de
  `reporte_ingresos` (cambio pequeño y aislado en `ReporteService`).
- (b) Dashboard hace las 4 llamadas y las combina — más lento, pero
  cero cambios a Reportes.

Mi recomendación: (a) — es un cambio de bajo riesgo y evita el
antipatrón de N llamadas para una sola tarjeta.

**No voy a decidir esto por mi cuenta — confírmame (a) o (b) para
cada hueco antes de la primera entrega de código.**

---

## 5. KPIs de la pantalla principal (contenido de `/dashboard/resumen`)

Mismos 9 KPIs ya aprobados en el diseño de Reportes (sección 7 de
`reportes-diseno.md`), ahora con su fuente exacta confirmada:

| KPI | Fuente |
|---|---|
| Ingresos de hoy (vs. ayer) | `reporte_ingresos` × 2 |
| Ingresos del mes (vs. mes anterior) | `reporte_ingresos` × 2 |
| Reservaciones activas | `reporte_reservaciones_por_estado` |
| Próximas 7 días | *nuevo cálculo simple, ver nota* |
| Saldo pendiente total | `reporte_cuentas_por_cobrar` |
| Tasa de cancelación (mes) | `reporte_cancelaciones` |
| Ocupación promedio (mes) | `reporte_ocupacion` (promedio de todos los servicios) |
| Diferencia de caja (hoy) | `CajaService.obtener_corte_dia` |
| Clientes nuevos (mes) | Hueco 1 (sección 4) |

**Nota sobre "Próximas 7 días":** ningún reporte actual filtra por
`fecha_visita` futura con un conteo simple — `reporte_ocupacion` sí
usa `fecha_visita` pero para otra cosa. Esto también es un hueco menor;
lo resuelvo igual que el Hueco 1 (mini-adición a Reportes) salvo que
me digas lo contrario.

---

## 6. Indicadores por cadencia

| Indicador | Diario | Semanal | Mensual |
|---|---|---|---|
| Ingresos | ✅ (tarjeta "hoy") | — | ✅ (tarjeta "mes") |
| Reservaciones por estado | — | — | ✅ |
| Ocupación | — | — | ✅ |
| Cuentas por cobrar | ✅ (snapshot siempre actual) | | |
| Corte de caja | ✅ | | |
| Cancelaciones | — | — | ✅ |
| Clientes nuevos | — | — | ✅ |

El Dashboard principal se enfoca en **hoy y este mes** — comparativas
semanales quedan disponibles vía `/reportes/*` con `periodo=semana`
para quien las necesite, pero no ocupan una tarjeta fija.

---

## 7. Tarjetas (cards) — contrato de datos exacto

Cada tarjeta es un objeto con esta forma común:

```
{
  "titulo": string,
  "valor": number | string,
  "comparacion_valor_anterior": number | null,
  "comparacion_porcentaje": number | null,
  "tendencia": "up" | "down" | "neutral" | null
}
```

Tarjetas de `/dashboard/resumen` (9, en el orden sugerido de
prioridad visual):

1. Ingresos hoy
2. Ingresos del mes
3. Reservaciones activas
4. Próximas 7 días
5. Saldo pendiente total
6. Tasa de cancelación (mes)
7. Ocupación promedio (mes)
8. Diferencia de caja (hoy)
9. Clientes nuevos (mes)

No se define aquí color/ícono/layout — eso es decisión de cada
cliente (React/PyQt/Flutter), no del backend.

---

## 8. Gráficas — qué serie de datos alimenta cada una

El backend entrega **datos**, no gráficas — cada cliente decide cómo
dibujarlas (explícitamente fuera de alcance de esta entrega, por tu
instrucción). Lo que sí define el backend es la forma de la serie:

| Gráfica sugerida | Endpoint que la alimenta | Forma de los datos |
|---|---|---|
| Línea: ingresos por día (mes actual) | `/dashboard/ingresos` | `serie: [{periodo, ingresos, reembolsos, neto}]` |
| Línea: tendencia de reservaciones | `/dashboard/reservaciones` | `serie: [{periodo, num_reservaciones}]` |
| Barras: reservaciones por estado | `/dashboard/reservaciones` | `por_estado: {estado: count}` |
| Barras: top 5 servicios vendidos | `/dashboard/servicios` | `items: [{servicio_nombre, num_reservaciones, total_facturado}]` |
| Barras: ocupación por servicio | `/dashboard/ocupacion` | `items: [{servicio_nombre, porcentaje_ocupacion_promedio}]` |
| Pastel: ingresos por método de pago | `/dashboard/ingresos` | Depende de cómo se resuelva el Hueco 2 |

---

## 9. Alertas — reglas exactas

Cada alerta es: `{tipo, severidad, mensaje, referencia_id}`.

| Alerta | Regla | Severidad |
|---|---|---|
| Cuenta por cobrar vieja | `reporte_cuentas_por_cobrar` con `antiguedad_minima_dias >= 15` (umbral configurable) | media |
| Reservación de hoy/mañana sin confirmar | `fecha_visita` en 0-1 días y `estado == "pendiente"` | alta |
| Caja con diferencia | Sesión cerrada hoy con `diferencia != 0` | media si `<50`, alta si `>=50` (umbral a confirmar) |
| Servicio sin reservas recientes | 0 reservaciones activas en los últimos 30 días (umbral a confirmar) | baja |
| Cancelación alta | `tasa_cancelacion` del mes `> 20%` (umbral a confirmar) | media |

Los umbrales exactos (15 días, $50, 20%, 30 días) son propuestas —
confírmalos o ajústalos antes de implementar; son literalmente una
constante en el código, cambiarlos después es trivial pero prefiero
que la primera versión ya tenga los números que tú quieres.

---

## 10. Qué consume cada cliente (React, PyQt, Flutter)

Los tres consumen **exactamente los mismos 8 endpoints** — no hay
lógica de negocio distinta por plataforma, solo distinta selección de
qué mostrar:

| Cliente | Uso típico |
|---|---|
| **React (portal web admin)** | Todos los endpoints — es la vista completa de administración, con gráficas y tablas detalladas. |
| **PyQt6 (app de escritorio, personal operativo)** | Principalmente `/dashboard/caja` y `/dashboard/alertas` — lo que el personal de recepción/caja necesita ver mientras trabaja, no las finanzas completas del mes. |
| **Flutter (móvil)** | Solo `/dashboard/resumen` y `/dashboard/alertas` — un vistazo rápido para el dueño/admin desde el celular, sin pretender reemplazar el portal completo. |

Esto sugiere una pregunta de control de acceso (ver sección 11).

---

## 11. Control de acceso — decisión pendiente

Reportes es 100% admin. El Dashboard tiene una mezcla:
- `/dashboard/resumen`, `/ingresos`, `/reservaciones`, `/ocupacion`,
  `/servicios`, `/clientes` → financieros/estratégicos → **admin**.
- `/dashboard/caja`, `/dashboard/alertas` → operativos, el personal
  de piso (cajero/operador) los necesita para trabajar, no solo el
  admin.

**Propuesta:** `/dashboard/caja` y `/dashboard/alertas` abiertos a
`admin`, `operador` y `cajero`; el resto solo `admin`. Confírmame si
esto es lo que quieres antes de implementar — es la primera vez que
un endpoint de este ecosistema se abre a roles no-admin además de la
protección genérica de JWT.

---

## 12. Siguiente paso

Antes de escribir código necesito que confirmes:
1. Hueco 1 (clientes nuevos): ¿(a) mini-entrega a Reportes, o (b) cálculo directo en Dashboard?
2. Hueco 2 (ingresos por método de pago): ¿(a) agregar `agrupar_por=metodo_pago` a Reportes, o (b) 4 llamadas desde Dashboard?
3. Umbrales de alertas (sección 9): ¿los propuestos están bien, o los ajustamos?
4. Control de acceso (sección 11): ¿apruebas abrir Caja/Alertas a operador/cajero?

Con eso resuelto, implementamos por entregas — probablemente:
Entrega 1 = `/dashboard/resumen` (el más valioso), Entrega 2 = el
resto de endpoints de detalle, Entrega 3 = `/dashboard/alertas`.
