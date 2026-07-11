# Mini-entrega: Permisos reales por rol en el backend

Hasta ahora, todas las rutas de negocio (Clientes, Reservaciones,
Servicios, Pagos, Caja) solo exigían "cualquier usuario autenticado y
activo" (`Depends(get_current_user)`). Reportes, `/auth/usuarios` y
`/dashboard/resumen` ya exigían rol `admin` específicamente. Esta
mini-entrega cierra esa diferencia: **la tabla de permisos ahora es
real en el backend, no solo una propuesta de UI.**

## Tabla de permisos aplicada

| Módulo | Roles permitidos | Antes |
|---|---|---|
| Clientes | `admin`, `operador` | cualquier autenticado |
| Reservaciones | `admin`, `operador` | cualquier autenticado |
| Servicios | `admin` | cualquier autenticado |
| Pagos | `admin`, `cajero` | cualquier autenticado |
| Caja | `admin`, `operador`, `cajero` | cualquier autenticado |
| Reportes | `admin` | ya era admin (sin cambio) |
| Usuarios (`/auth/usuarios`) | `admin` | ya era admin (sin cambio) |
| Dashboard `/resumen` | `admin` | ya era admin (sin cambio) |

## Cambio técnico

En cada uno de los 5 routers afectados, se cambió:

```python
dependencies=[Depends(get_current_user)]
```

por:

```python
dependencies=[Depends(require_roles("admin", "operador"))]  # roles según el módulo
```

`require_roles` ya existía desde el módulo Auth (usado en
`/auth/usuarios`) — no se creó ningún mecanismo nuevo, solo se aplicó
el que ya estaba probado.

**No se tocó ninguna lógica de negocio.** Ningún `Service` ni
`Repository` cambió — el cambio es exclusivamente en la capa de rutas.

## Archivos modificados

- `app/routes/cliente_routes.py`
- `app/routes/reservacion_routes.py`
- `app/routes/servicio_routes.py`
- `app/routes/pago_routes.py`
- `app/routes/caja_routes.py`

## Bug que esto iba a causar, y que se corrigió en los tests

Los tests de Reservaciones, Pagos, Servicios y Caja autenticaban su
cliente de prueba por defecto con un rol **inventado**
(`"admin_auth_test"`) que nunca correspondía a ningún rol real del
sistema — funcionaba antes porque la única regla era "estar
autenticado", sin importar el nombre del rol. Con `require_roles` real,
ese nombre de rol ya no est en ninguna lista permitida, así que los 63
tests de esos 4 archivos habrían fallado con `403` en cascada.

**Se corrigió renombrando ese rol a `"admin"` en los 4 fixtures** (rol
que siempre tiene acceso a todo) — ningún test individual cambió su
lógica, solo el nombre del rol del usuario autenticado por defecto.

## Tests nuevos de permisos (11)

- Clientes: operador puede listar (200), cajero no puede (403), sin token (401).
- Reservaciones: operador puede listar (200), cajero no puede (403).
- Pagos: cajero puede listar (200), operador no puede (403).
- Servicios: operador no puede acceder (403), admin sí puede (200).
- Caja: operador puede acceder (200), cajero puede acceder (200), un rol inventado no puede (403).

## Cómo correr las pruebas

```bash
pytest tests/ -v
# Esperado: 164 passed (15+20+12+13+15+61+13+15)
```

## Importante para el Frontend (React)

La tabla de la sección 11 de `docs/frontend/frontend-diseno.md` ya no
es "solo propuesta de UI" — ahora es el comportamiento real del
backend. React debe ocultar/mostrar navegación según esta misma tabla,
y además debe manejar el `403` real que el backend devolverá si algún
usuario intenta acceder a algo fuera de su rol (aunque la UI ya lo
oculte, un 403 real puede llegar si alguien manipula la URL
directamente — el frontend debe redirigir a `/no-autorizado` en ese
caso, no solo asumir que nunca pasará).
