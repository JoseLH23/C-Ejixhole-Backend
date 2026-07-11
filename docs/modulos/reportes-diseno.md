# Diseño de Arquitectura — Módulo Reportes
### EjiXhole Experience OS

---

## 0. Principio rector

Reportes **no introduce datos nuevos** — es una capa de **lectura y
agregación** sobre las tablas que ya existen (`clientes`, `servicios`,
`reservaciones`, `pagos`, `caja_sesiones`, `caja_movimientos`,
`usuarios`). No se proponen tablas nuevas. Si en el futuro el volumen
de datos lo justifica, se puede agregar una tabla de snapshots
pre-calculados — pero eso es optimización de rendimiento, no parte de
este diseño inicial.

Sigue la misma arquitectura que los demás módulos: **Repository →
Service → Routes**, sin modelos nuevos (solo queries de agregación
sobre los modelos existentes).

---

## 1. Riesgo técnico conocido — decisión de diseño obligatoria

En Clientes, Reservaciones, Pagos y Caja ya nos topamos tres veces con
comportamiento distinto entre SQLite (tests) y Postgres (producción):
fechas como string vs objeto, escala de `Decimal`, y comparación de
`DateTime` con timezone. Reportes es el módulo con **más riesgo de
este tipo de bug**, porque agrupar por día/semana/mes normalmente se
hace con funciones de fecha específicas del motor (`date_trunc` en
Postgres no existe igual en SQLite).

**Decisión:** todo el agrupamiento por periodo (día/semana/mes/año) se
hace **en Python, no en SQL**. Las queries a la base de datos solo
traen los registros crudos filtrados por rango de fechas (`desde`/
`hasta`); el `Service` los agrupa y suma. Es el mismo patrón ya usado
en `CajaService.obtener_corte_dia`. Es menos eficiente que agregar en
SQL para volúmenes enormes, pero para un parque (cientos o miles de
registros, no millones) es irrelevante en rendimiento y elimina una
categoría entera de bugs silenciosos entre entornos.

---

## 2. Control de acceso

Reportes expone información financiera y de rendimiento de usuarios —
más sensible que un CRUD normal. Propuesta (a confirmar antes de
implementar):

- **Todos los endpoints de Reportes requieren rol `admin`.**
- Si más adelante se quiere que `operador`/`cajero` vean reportes
  operativos (no financieros), se puede abrir por endpoint específico
  — no se abre nada por default.

---

## 3. Catálogo de reportes

### A. Financieros

| Reporte | Qué responde | Fuente |
|---|---|---|
| Ingresos por periodo | ¿Cuánto entró, agrupado por día/semana/mes/método de pago/servicio? | `pagos` |
| Cuentas por cobrar | ¿Qué reservaciones tienen saldo pendiente, y de qué antigüedad? | `reservaciones` (saldo_pendiente > 0) |
| Corte de caja consolidado | Ingresos/egresos/diferencias agregando varias sesiones de caja en un rango | `caja_sesiones`, `caja_movimientos` |
| Diferencias de caja históricas | ¿Qué usuarios tienen faltantes/sobrantes recurrentes al cerrar caja? | `caja_sesiones.diferencia` |

### B. Operacionales (Reservaciones)

| Reporte | Qué responde | Fuente |
|---|---|---|
| Reservaciones por estado | ¿Cuántas pendientes/confirmadas/completadas/canceladas en un periodo? | `reservaciones` |
| Tasa de cancelación | % de reservaciones canceladas sobre el total del periodo | `reservaciones` |
| Ocupación por servicio | Personas reservadas vs. capacidad_maxima, por servicio y periodo | `reservaciones` + `servicios` |
| Reservaciones por origen | ¿De dónde vienen? (recepción, recepción express, portal, teléfono) | `reservaciones` |
| Agenda próxima | Reservaciones confirmadas con fecha_visita futura | `reservaciones` |

### C. Clientes

| Reporte | Qué responde | Fuente |
|---|---|---|
| Clientes nuevos por periodo | ¿Cuántos clientes se registraron? | `clientes.fecha_creacion` |
| Nuevos vs. recurrentes | % de reservaciones de clientes con 1 vs. 2+ reservaciones históricas | `clientes` + `reservaciones` |
| Top clientes por gasto | Ranking por suma de pagos asociados a sus reservaciones | `clientes` + `pagos` |

### D. Servicios

| Reporte | Qué responde | Fuente |
|---|---|---|
| Servicios más reservados | Ranking por número de reservaciones en el periodo | `servicios` + `reservaciones` |
| Servicios por ingreso generado | Ranking por suma de `reservaciones.total` (o pagos reales) | `servicios` + `reservaciones`/`pagos` |

### E. Usuarios / Rendimiento operativo

| Reporte | Qué responde | Fuente |
|---|---|---|
| Rendimiento por usuario | Reservaciones creadas, pagos gestionados, diferencias de caja, por usuario y periodo | `reservaciones`, `pagos`, `caja_sesiones` filtrados por `usuario_id` |

---

## 4. Consultas reutilizables (bloques base en `ReporteRepository`)

Estas son las funciones de bajo nivel que todos los reportes combinan.
Ningún reporte reimplementa su propia query desde cero:

- `obtener_pagos_en_rango(desde, hasta, tipo=None, metodo_pago=None)`
- `obtener_reservaciones_en_rango(desde, hasta, estado=None, servicio_id=None, origen=None)` — filtra por `fecha_visita` o por `fecha_creacion` según el reporte (se especifica cuál en cada endpoint)
- `obtener_clientes_creados_en_rango(desde, hasta)`
- `obtener_sesiones_caja_en_rango(desde, hasta, usuario_id=None)`
- `contar_reservaciones_historicas_por_cliente(cliente_ids)` — para distinguir nuevo vs. recurrente

Cada `Service` de reporte combina estas funciones y agrega en Python
(ver sección 1).

---

## 5. Filtros por reporte

Todos los reportes de rango de fechas aceptan:
- `desde` (date, opcional — default: inicio del mes actual)
- `hasta` (date, opcional — default: hoy)
- `periodo` (opcional, atajo): `hoy` | `semana` | `mes` | `anio` — si se manda, el Service calcula `desde`/`hasta` automáticamente y este parámetro gana sobre `desde`/`hasta` manuales.
- `agrupar_por` (opcional, cuando aplica): `dia` | `semana` | `mes` — determina el tamaño del bucket en la serie de resultados.

Filtros específicos adicionales:

| Reporte | Filtros propios |
|---|---|
| Ingresos | `metodo_pago`, `servicio_id` |
| Reservaciones por estado | `estado`, `servicio_id`, `origen` |
| Ocupación | `servicio_id` (opcional; si no se manda, todos) |
| Top clientes / Top servicios | `limit` (default 10) |
| Cuentas por cobrar | `antiguedad_minima_dias` (opcional) |
| Rendimiento por usuario | `usuario_id` (si no se manda, todos los usuarios) |

---

## 6. Endpoints propuestos

```
GET /reportes/ingresos
GET /reportes/cuentas-por-cobrar
GET /reportes/caja/resumen
GET /reportes/caja/diferencias
GET /reportes/reservaciones
GET /reportes/reservaciones/ocupacion
GET /reportes/reservaciones/agenda
GET /reportes/clientes/nuevos
GET /reportes/clientes/top
GET /reportes/servicios/top
GET /reportes/usuarios/rendimiento
GET /reportes/dashboard
```

Todos bajo `dependencies=[Depends(require_roles("admin"))]` (ver
sección 2). Todos devuelven JSON; ninguno modifica datos (son
`GET` puros, sin efectos secundarios).

### `/reportes/dashboard` — el endpoint que consume el Dashboard

En vez de que el Dashboard haga 10 llamadas separadas al cargar,
**un solo endpoint agregado** devuelve el set curado de KPIs (sección
7) para la pantalla principal. Los reportes detallados (con filtros,
series por día, etc.) se consultan aparte, bajo demanda, cuando el
admin entra a una sección específica del Dashboard.

---

## 7. KPIs para administradores (contenido de `/reportes/dashboard`)

| KPI | Cálculo | Comparación |
|---|---|---|
| Ingresos de hoy | Suma de pagos (no reembolsos) de hoy | vs. mismo día semana pasada |
| Ingresos del mes | Suma de pagos del mes actual | vs. mes anterior |
| Reservaciones activas | Count `estado IN (pendiente, confirmada)` | — |
| Próximas 7 días | Count reservaciones confirmadas con fecha_visita en los próximos 7 días | — |
| Saldo pendiente total | Suma de `saldo_pendiente` de reservaciones activas | — |
| Tasa de cancelación (mes) | canceladas / total del mes | vs. mes anterior |
| Ocupación promedio (mes) | promedio de personas/capacidad_maxima en reservaciones del mes | — |
| Diferencia de caja acumulada (mes) | suma de `diferencia` en sesiones cerradas del mes | — |
| Clientes nuevos (mes) | count clientes creados este mes | vs. mes anterior |

---

## 8. Periodicidad — qué existe a qué cadencia

No se crean endpoints separados por periodicidad (`/reportes/ingresos/diario`,
`/mensual`, etc.) — un mismo endpoint sirve todas las cadencias vía
`periodo` o `desde`/`hasta` + `agrupar_por` (sección 5). Esta tabla
documenta qué combinaciones tienen sentido de negocio real:

| Reporte | Diario | Semanal | Mensual | Anual |
|---|---|---|---|---|
| Ingresos | ✅ (corte de caja) | ✅ | ✅ | ✅ |
| Reservaciones por estado | ✅ | ✅ | ✅ | ✅ |
| Ocupación | — | ✅ | ✅ | ✅ |
| Cuentas por cobrar | ✅ (snapshot del momento, no tiene "periodo") | | | |
| Corte de caja | ✅ (uno por sesión/día) | ✅ (agregado) | ✅ (agregado) | — (poco útil) |
| Clientes nuevos | ✅ | ✅ | ✅ | ✅ |
| Top clientes / servicios | — | — | ✅ | ✅ |
| Rendimiento por usuario | ✅ | ✅ | ✅ | — |

---

## 9. Qué consume el Dashboard, y cómo

1. **Al cargar la pantalla principal**: una sola llamada a
   `GET /reportes/dashboard` → pinta las tarjetas de KPIs (sección 7).
2. **Al entrar a una sección específica** (ej. "Ingresos"): llamada a
   `GET /reportes/ingresos?periodo=mes&agrupar_por=dia` → pinta una
   gráfica de serie diaria del mes.
3. **Filtros interactivos** (el admin cambia el rango de fechas en la
   UI): el Dashboard vuelve a llamar el mismo endpoint con nuevos
   `desde`/`hasta` — no hay endpoints distintos por filtro.
4. Las apps cliente futuras (PyQt6, Flutter, portal web) reutilizan
   **exactamente estos mismos endpoints** — no hay una capa de
   reportes distinta para cada cliente.

---

## 10. Fuera de alcance (a propósito)

- Exportar a PDF/Excel — se puede agregar después como una capa encima
  de estos mismos endpoints (formatear lo que ya existe), no requiere
  rediseño.
- Comparativas año contra año más allá de lo listado en KPIs.
- Snapshots pre-calculados / cacheados — solo si el rendimiento real
  lo exige más adelante; hoy no hay evidencia de que se necesite.
- Cualquier integración con MH-Core / IA — Reportes de EjiXhole es
  puramente analítico sobre datos propios, no usa el cerebro de
  MindHigh (son proyectos independientes, como ya se acordó).

---

## 11. Siguiente paso

Con este documento aprobado, la implementación seguiría el orden:
1. `ReporteRepository` (las consultas base de la sección 4).
2. `ReporteService` (agregación en Python por periodo).
3. Reportes financieros primero (Ingresos, Cuentas por cobrar) — son
   los de mayor valor inmediato.
4. `/reportes/dashboard` al final, una vez que los reportes
   individuales que agrega ya existan y estén probados.
