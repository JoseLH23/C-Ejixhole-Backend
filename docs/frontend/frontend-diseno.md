# Diseño de Arquitectura — Frontend React
### EjiXhole Experience OS

---

## 0. Principio rector

El frontend **no contiene lógica de negocio**. Todas las reglas
(duplicados, saldo, una reservación activa, umbrales de alertas) ya
viven en el backend y ya están probadas. React solo:
1. Llama a la API.
2. Muestra los datos.
3. Valida lo mínimo indispensable en formularios (tipos, campos
   requeridos) para dar feedback rápido — nunca reemplaza la
   validación del backend, solo la anticipa.
4. Oculta/muestra UI según el rol — pero la autorización real la
   sigue garantizando el backend con 401/403.

---

## 1. Arquitectura general

SPA (Single Page Application) con Vite + React. Arquitectura por
capas:

```
Pantallas (features/)
      │
Hooks de datos (useQuery/useMutation, uno por recurso)
      │
Cliente API (api/, un archivo por módulo backend)
      │
Backend FastAPI
```

**Server state vs. UI state, separados explícitamente:**
- *Server state* (datos que vienen del backend: clientes, reservaciones,
  reportes) → TanStack Query. Nunca se duplica en un store global — se
  vuelve a pedir o se invalida cache cuando cambia.
- *UI state* (modal abierto, filtro seleccionado, sidebar colapsado) →
  `useState`/Context local, sin librería extra.
- *Estado de sesión* (usuario, rol, token) → un solo `AuthContext`.

No se usa Redux — con TanStack Query + Context alcanza para el tamaño
de esta app, y evita la complejidad de mantener sincronizado un store
global con el backend.

---

## 2. Organización de carpetas

```
src/
  api/                     # un archivo por módulo backend, funciones puras
    client.ts              # instancia de axios + interceptores JWT
    auth.ts
    clientes.ts
    reservaciones.ts
    pagos.ts
    servicios.ts
    caja.ts
    reportes.ts
    dashboard.ts

  types/                   # tipos TS reflejando los schemas Pydantic
    cliente.ts
    reservacion.ts
    pago.ts
    servicio.ts
    caja.ts
    reporte.ts
    dashboard.ts
    auth.ts

  features/                # un folder por módulo de negocio (mismo mapeo que el backend)
    auth/
      LoginPage.tsx
      useAuth.ts
    dashboard/
      DashboardPage.tsx
      KpiCard.tsx
    clientes/
      ClientesListPage.tsx
      ClienteFormModal.tsx
      ClienteDetallePage.tsx
      useClientes.ts
    reservaciones/
      ReservacionesListPage.tsx
      ReservacionFormModal.tsx
      ReservacionDetallePage.tsx
      useReservaciones.ts
    pagos/
      RegistrarPagoModal.tsx
      HistorialPagos.tsx
      usePagos.ts
    servicios/
      ServiciosListPage.tsx
      ServicioFormModal.tsx
      useServicios.ts
    caja/
      CajaPage.tsx
      AbrirCajaModal.tsx
      CerrarCajaModal.tsx
      useCaja.ts
    reportes/
      ReportesHubPage.tsx      # menú de los 12 reportes
      IngresosReportPage.tsx
      CuentasPorCobrarReportPage.tsx
      OcupacionReportPage.tsx
      ... (uno por reporte, o uno genérico parametrizado — ver sección 9)
      useReportes.ts
    usuarios/                    # gestión de usuarios, solo admin
      UsuariosListPage.tsx
      useUsuarios.ts

  components/               # reutilizables SIN lógica de negocio
    ui/
      Button.tsx
      Input.tsx
      Select.tsx
      DatePicker.tsx
      DateRangeFilter.tsx    # el filtro periodo/desde/hasta que se repite en TODOS los reportes
      Table.tsx              # tabla genérica con paginación/orden
      Modal.tsx
      Card.tsx
      Badge.tsx              # para estados (pendiente/confirmada/...), colores centralizados
      Toast.tsx
      LoadingSpinner.tsx
      EmptyState.tsx
      ConfirmDialog.tsx
      MoneyDisplay.tsx       # formatea "500.00" (string del backend) a "$500.00 MXN"
    layout/
      AppShell.tsx           # Sidebar + Topbar + <Outlet/>
      Sidebar.tsx
      Topbar.tsx

  hooks/                    # genéricos, no ligados a un módulo
    useDebounce.ts
    usePagination.ts

  context/
    AuthContext.tsx

  router/
    AppRouter.tsx
    RequireAuth.tsx
    RequireRole.tsx

  utils/
    formatters.ts           # fechas, moneda
    constants.ts            # ESTADOS_RESERVACION, TIPOS_PAGO, etc. — espejo de las constantes del backend

  App.tsx
  main.tsx
```

**Por qué feature-based y no type-based** (`pages/`, `components/`
todo junto): cada carpeta de `features/` mapea 1:1 a un módulo del
backend (mismo nombre, mismas reglas). Esto hace que cualquier cambio
de API (ej. Reportes Entrega 3) tenga un lugar obvio dónde vivir en el
frontend, sin tener que buscar en carpetas genéricas.

---

## 3. Componentes reutilizables (contrato, no diseño visual)

| Componente | Responsabilidad |
|---|---|
| `Table` | Tabla genérica: columnas configurables, paginación, orden. La usan Clientes, Reservaciones, Servicios, Pagos, listados de Reportes. |
| `DateRangeFilter` | `periodo` (hoy/semana/mes/año) + `desde`/`hasta` manuales — idéntico en los 12 reportes y en varios listados. Un solo componente, no 12 copias. |
| `Badge` | Colorea estados: `pendiente` (amarillo), `confirmada` (azul), `completada` (verde), `cancelada` (gris/rojo). Un solo mapeo estado→color, no repetido en cada pantalla. |
| `MoneyDisplay` | Recibe el string `"500.00"` que ya devuelve el backend (Decimal serializado) y lo formatea a moneda — nunca hace matemática, solo formatea. |
| `KpiCard` | Renderiza exactamente el contrato de `TarjetaOut` del Dashboard (`titulo`, `valor`, `comparacion_porcentaje`, `tendencia`) — un componente, reutilizado para las 9 tarjetas actuales y las que se agreguen. |
| `ConfirmDialog` | Confirmaciones antes de acciones destructivas o irreversibles (cancelar reservación, desactivar cliente/servicio). |
| `EmptyState` | Mensaje consistente cuando una lista/reporte no tiene datos — evita pantallas en blanco confusas. |

---

## 4. Layout principal

```
┌─────────────────────────────────────────┐
│ Topbar: logo · nombre de usuario · rol · logout │
├───────────┬─────────────────────────────┤
│           │                             │
│  Sidebar  │      <Outlet /> (contenido) │
│ (nav por  │                             │
│   rol)    │                             │
│           │                             │
└───────────┴─────────────────────────────┘
```

- `AppShell` envuelve todas las rutas autenticadas.
- `Sidebar` arma su lista de links dinámicamente según el rol del
  usuario en `AuthContext` (ver sección 11) — no hay una versión
  distinta del Sidebar por rol, es la misma lógica con distinto input.
- `Topbar` muestra alertas activas (badge con contador) una vez que
  `/dashboard/alertas` exista — por ahora, solo usuario/rol/logout.

---

## 5. Sistema de navegación

React Router v6, rutas anidadas bajo `AppShell`:

```
/login                          (pública)
/                                → redirige a /dashboard
/dashboard                       (todos los roles autenticados)
/clientes                        (admin, operador)
/clientes/:id                    (admin, operador)
/reservaciones                   (admin, operador)
/reservaciones/:id                (admin, operador)
/servicios                       (admin)
/pagos                           (admin, cajero)
/caja                            (admin, operador, cajero)
/reportes                        (admin) — hub con los 12
/reportes/ingresos               (admin)
/reportes/...                    (admin, uno por reporte)
/usuarios                        (admin)
/no-autorizado
*                                 404
```

`RequireAuth` valida sesión (token presente y no expirado);
`RequireRole` valida el rol contra la lista permitida de la ruta —
si no cumple, redirige a `/no-autorizado`, no a un error genérico.

---

## 6. Pantallas

1. **Login** — email + password, llama `POST /auth/login`.
2. **Dashboard** — 9 `KpiCard` de `/dashboard/resumen`, accesos rápidos a Reservaciones/Caja.
3. **Clientes (lista)** — tabla + búsqueda + botón "Nuevo cliente" (modal, muestra `posibles_duplicados` si el backend los devuelve).
4. **Cliente (detalle)** — datos + historial de sus reservaciones.
5. **Reservaciones (lista)** — tabla filtrable por estado/servicio + botón "Nueva reservación".
6. **Reservación (detalle)** — datos, saldo pendiente, botón "Registrar pago", botón "Cambiar estado".
7. **Registrar pago (modal)** — se abre desde el detalle de una reservación.
8. **Servicios (lista + form)** — catálogo, crear/editar/desactivar.
9. **Caja** — estado actual (abierta/cerrada), botón abrir/cerrar, tabla de movimientos, botón "Registrar ingreso/egreso".
10. **Reportes (hub)** — menú de los 12 reportes disponibles.
11. **Reporte individual** (×12) — `DateRangeFilter` + filtros propios + tabla o gráfica según la forma de la respuesta (serie vs. items).
12. **Usuarios** — solo admin, alta de usuarios y asignación de rol.
13. **No autorizado / 404**.

---

## 7. Flujo entre pantallas (journeys clave)

**Login → Dashboard**
Login exitoso guarda token → redirige a `/dashboard`.

**Crear una reservación completa**
`Reservaciones` → "Nueva" → busca cliente (o crea uno inline, si
`posibles_duplicados` viene no vacío se muestra una advertencia antes
de confirmar) → selecciona servicio y fecha → confirma → vuelve al
detalle de la reservación creada.

**Cobrar una reservación**
Detalle de reservación → "Registrar pago" → modal con monto/tipo/método
→ al guardar, se invalida la cache de la reservación (TanStack Query)
para que `saldo_pendiente` y `estado` se actualicen sin recargar la
página.

**Operar caja**
Al entrar a `/caja`: si el usuario no tiene sesión abierta, se muestra
únicamente el botón "Abrir caja" (el resto de la pantalla deshabilitado)
— esto es una decisión de UX, no del backend, que ya rechaza con 409
si se intenta abrir dos veces; el frontend solo evita que el usuario
llegue a ese error.

**Explorar un reporte**
`Reportes` (hub) → clic en "Ingresos" → `DateRangeFilter` con default
`periodo=mes` → tabla/gráfica se actualiza reactivamente al cambiar
filtros (sin botón "Buscar" — refetch automático vía TanStack Query
al cambiar los parámetros del hook).

---

## 8. Consumo de Dashboard API

Única llamada disponible hoy: `GET /dashboard/resumen`.

```ts
// features/dashboard/useDashboard.ts
export function useDashboardResumen() {
  return useQuery({
    queryKey: ["dashboard", "resumen"],
    queryFn: () => api.dashboard.getResumen(),
    staleTime: 60_000, // 1 minuto — no tiene sentido más tiempo real que eso para KPIs
  });
}
```

`DashboardPage` renderiza `data.tarjetas.map(t => <KpiCard {...t} />)`
— **sin lógica de formato específica por tarjeta**: `KpiCard` ya sabe
interpretar `valor`/`comparacion_porcentaje`/`tendencia` de forma
genérica (flecha arriba/abajo, color verde/rojo) sin importar cuál de
las 9 tarjetas sea. Cuando se agreguen `/dashboard/ingresos`,
`/dashboard/caja`, etc. en las siguientes entregas, alimentan
secciones adicionales de la misma página o pestañas — no requieren
una arquitectura distinta.

---

## 9. Consumo de Reportes

Los 12 reportes comparten una de dos formas de respuesta:
- **Serie** (`{desde, hasta, ..., serie: [...]}`) → se renderiza con
  un componente `SerieChart` genérico (línea o barras según el reporte).
- **Items** (`{..., items: [...]}`) → se renderiza con `Table`
  genérica, columnas configuradas por reporte (no una tabla por
  reporte, un `columns` array por reporte pasado a la misma `Table`).

Se recomienda una página genérica parametrizada en vez de 12
componentes casi idénticos:

```ts
// reportes/reportesConfig.ts
export const REPORTES = {
  ingresos: { endpoint: "ingresos", tipo: "serie", filtros: [...] },
  "cuentas-por-cobrar": { endpoint: "cuentas-por-cobrar", tipo: "items", columnas: [...] },
  // ... los 12
};

// reportes/ReportePage.tsx — una sola página, recibe la clave por ruta
function ReportePage() {
  const { reporteId } = useParams();
  const config = REPORTES[reporteId];
  const { data } = useReporte(config.endpoint, filtros);
  return config.tipo === "serie" ? <SerieChart data={data.serie} /> : <Table data={data.items} columns={config.columnas} />;
}
```

Esto evita mantener 12 archivos casi idénticos y hace trivial agregar
el reporte #13 si Reportes crece más.

---

## 10. Sistema de autenticación JWT

1. `POST /auth/login` → `{access_token, token_type}`.
2. El token se guarda en `localStorage` (app interna, no pública —
   aceptable; si se expone a internet abierta en el futuro, reevaluar
   `httpOnly cookie` en vez de `localStorage`, que es más resistente a
   XSS pero requiere cambios en el backend para setear la cookie).
3. `AuthContext` mantiene `{usuario, rol, token, isAuthenticated}` y
   expone `login()`/`logout()`.
4. Interceptor de **request** en `api/client.ts`: agrega
   `Authorization: Bearer <token>` a toda llamada automáticamente —
   ninguna función de `api/*.ts` necesita saber del token.
5. Interceptor de **response**: si llega un `401`, limpia sesión y
   redirige a `/login` — cubre tanto "nunca tuvo token" como "el token
   expiró a la mitad de la sesión".
6. Al cargar la app (`main.tsx`/`App.tsx`): si hay token en
   `localStorage`, se decodifica (solo lectura del payload, con
   `jwt-decode`, **nunca se verifica firma en el cliente** — eso es
   responsabilidad exclusiva del backend) para leer `exp` y `rol`. Si
   ya expiró, se descarta sin llamar al backend.

---

## 11. Manejo de permisos por rol

Refleja exactamente lo que el backend ya protege — el frontend no
inventa reglas nuevas, solo las espeja para UX:

| Ruta / sección | admin | operador | cajero |
|---|---|---|---|
| Dashboard | ✅ | ✅ | ✅ |
| Clientes | ✅ | ✅ | ❌ |
| Reservaciones | ✅ | ✅ | ❌ |
| Servicios | ✅ | ❌ | ❌ |
| Pagos | ✅ | ❌ | ✅ |
| Caja | ✅ | ✅ | ✅ |
| Reportes | ✅ | ❌ | ❌ |
| Usuarios | ✅ | ❌ | ❌ |

**Nota importante:** hoy el backend protege Clientes/Reservaciones/
Servicios/Pagos/Caja/Reportes solo con "cualquier usuario autenticado"
(`get_current_user`), **no** con restricción de rol específico (eso
solo existe para `/auth/usuarios` y, cuando se implementen,
`/dashboard/*`). Esta tabla es la propuesta de **cómo debería verse la
UI** — implementarla del lado del backend con `require_roles(...)` en
cada router (si se decide) es una tarea de backend aparte, fuera de
este documento de frontend. Mientras tanto, el frontend puede ocultar
secciones por rol aunque el backend técnicamente las permita a
cualquier autenticado — es una capa de UX, no de seguridad real, hasta
que el backend también las restrinja.

`RequireRole` implementación conceptual:
```tsx
<RequireRole roles={["admin", "operador"]}>
  <ReservacionesListPage />
</RequireRole>
```

---

## 12. Librerías recomendadas

| Necesidad | Librería | Por qué |
|---|---|---|
| Build/dev server | Vite | Ya definido en el stack original del proyecto. |
| Routing | React Router v6 | Estándar, rutas anidadas + guards simples. |
| Data fetching/cache | TanStack Query | Cache automático, refetch, invalidación — evita reinventar loading/error states a mano en cada pantalla. |
| HTTP client | Axios | Interceptores maduros para JWT (fetch nativo requiere más código repetido). |
| Formularios | React Hook Form + Zod | Validación declarativa, poco boilerplate, Zod además sirve como documentación viva de la forma esperada. |
| Estilos | Tailwind CSS + shadcn/ui | Velocidad de desarrollo sin sacrificar consistencia visual; shadcn/ui da componentes base (Modal, Table, Badge) ya accesibles. |
| Gráficas | Recharts | Liviano, suficiente para líneas/barras de los reportes — no se necesita algo más pesado. |
| Fechas | date-fns | Manejo de fechas sin el peso de moment.js. |
| Decodificar JWT | jwt-decode | Solo lectura de payload, no verificación. |

---

## 13. Estrategia para que PyQt y Flutter reutilicen la misma API

**Regla base:** ningún cliente (React, PyQt, Flutter) reimplementa
lógica de negocio. Los tres son "tontos" — solo React, PyQt y Flutter
distintos consumiendo el mismo contrato.

1. **Fuente de verdad única del contrato: el OpenAPI que FastAPI ya
   genera solo.** `/openapi.json` (y `/docs` para explorarlo) reflejan
   automáticamente cada schema Pydantic, cada endpoint, cada código de
   error. En vez de que cada plataforma "adivine" la forma de la
   respuesta, se generan tipos/modelos a partir de ese spec:
   - React: `openapi-typescript` genera los tipos TS directo del JSON.
   - PyQt (Python): los modelos Pydantic del backend pueden importarse
     directamente si PyQt corre en el mismo entorno Python, o generarse
     con `datamodel-code-generator` si es un proceso separado.
   - Flutter (Dart): `openapi-generator` con el generador de Dart.

   Esto evita el bug clásico de "el frontend espera `monto_pagado`
   pero el backend cambió a `monto_pagada`" — se detecta al regenerar
   tipos, no en producción.

2. **Mismo esquema de auth en los tres:** login → JWT → header
   `Authorization: Bearer`. PyQt y Flutter implementan su propio
   interceptor/wrapper HTTP con la misma lógica que la sección 10
   (guardar token, adjuntarlo, manejar 401).

3. **Mismo mapeo de roles → permisos de UI** (sección 11), cada
   plataforma lo aplica con su propio mecanismo de routing/guards, pero
   la tabla de qué rol ve qué es una sola fuente compartida (se puede
   literalmente copiar esa tabla a la documentación de cada cliente).

4. **Alcance por plataforma ya decidido en `dashboard-diseno.md`
   (sección 10)** — se reafirma aquí:
   - **React**: todas las pantallas, todos los reportes — el portal de
     administración completo.
   - **PyQt6**: pantallas operativas del día a día para el personal en
     el parque — Caja, Reservaciones, Clientes, Pagos. No necesita el
     hub completo de Reportes.
   - **Flutter**: vista rápida desde el celular para el dueño/admin —
     `/dashboard/resumen` y `/dashboard/alertas` (cuando exista),
     posiblemente Caja en modo consulta. No es una versión reducida de
     React, es una app con un propósito distinto (revisar, no operar).

5. **Errores del backend se interpretan igual en los tres:** un 409
   siempre significa "conflicto de regla de negocio, muestra el
   `detail` tal cual"; un 422 siempre significa "error de validación
   de formulario, resalta el campo"; un 401 siempre significa "sesión
   expirada, vuelve a login". Esta tabla de interpretación de códigos
   HTTP debería documentarse una sola vez y aplicarse igual en los tres
   clientes, para que el comportamiento ante errores sea predecible sin
   importar la plataforma.

---

## 14. Siguiente paso

Con esto aprobado, se implementa por entregas — sugerido:
1. Setup del proyecto + `api/client.ts` + `AuthContext` + Login + `AppShell`/routing base.
2. Dashboard (única pantalla real de datos, valida que toda la cadena JWT → API → UI funciona).
3. Clientes (CRUD completo, primer módulo con formularios reales).
4. Reservaciones + Pagos (el flujo de negocio central).
5. Servicios + Caja.
6. Reportes (los 12, con el patrón genérico de la sección 9).
7. Usuarios (admin).

Cada entrega, igual que en el backend: código + pruebas (aquí,
pruebas de componente/integración con Vitest + Testing Library) +
verificación de que lo anterior sigue funcionando antes de avanzar.
