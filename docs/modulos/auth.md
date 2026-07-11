# Módulo Auth/Usuarios — Activado

## Qué cambió respecto al esqueleto anterior

1. `app/main.py` — se registró `auth_routes`.
2. **Las 4 rutas de negocio (Clientes, Reservaciones, Pagos, Servicios)
   ahora exigen un JWT válido** en cada request:
   `dependencies=[Depends(get_current_user)]` en cada `APIRouter(...)`.
   Cualquier rol autenticado y activo puede usarlas — no hay
   restricción por rol en estos 4 módulos todavía (ver "Fuera de
   alcance" abajo).
3. Se agregó `scripts/create_admin.py` para crear el primer usuario
   admin (problema de "huevo y gallina": `POST /auth/usuarios` exige
   rol admin, y al inicio no existe ningún admin).

## Endpoints

| Método | Ruta             | Protección |
|--------|-------------------|------------|
| POST   | `/auth/login`     | Ninguna (es el punto de entrada) |
| POST   | `/auth/usuarios`  | Requiere rol `admin` |

## Cómo obtener tu primer token

```bash
# 1. Crea el primer admin (una sola vez, con Postgres real corriendo)
python -m scripts.create_admin

# 2. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "tu@email.com", "password": "tu-password"}'

# Respuesta: {"access_token": "eyJ...", "token_type": "bearer"}

# 3. Usar el token en cualquier ruta protegida
curl http://localhost:8000/clientes \
  -H "Authorization: Bearer eyJ..."
```

En Swagger (`/docs`): botón **Authorize** (candado arriba a la derecha)
→ pega el token (sin la palabra "Bearer", Swagger la agrega sola en
el campo `Value`) → todas las pruebas desde Swagger quedan autenticadas.

## Impacto en los tests existentes (ya resuelto)

Proteger las rutas rompe los 46 tests anteriores si siguen llamando a
los endpoints sin token. La solución fue **modificar solo el fixture
`client` de cada archivo de test** (no el cuerpo de ningún test):
ahora crea un usuario de prueba y arma el `TestClient` con el header
`Authorization` puesto por defecto en cada request.

Archivos de test modificados (solo el fixture `client`):
- `tests/test_clientes.py`
- `tests/test_reservaciones.py`
- `tests/test_pagos.py`
- `tests/test_servicios.py`

## Decisiones de diseño

- **Cualquier rol autenticado puede usar Clientes/Reservaciones/Pagos/Servicios.**
  No se agregó restricción por rol (ej. "solo cajero puede pagar") porque
  no se definió esa regla de negocio explícitamente. Es fácil agregarla
  después: cambiar `Depends(get_current_user)` por
  `Depends(require_roles("cajero", "admin"))` en el router que corresponda.
- **`usuario_id` en Reservaciones/Pagos sigue viniendo en el body**, no
  se tomó del token todavía — cambiarlo es una modificación futura
  aislada en `reservacion_service.py`/`pago_service.py` y sus rutas.
- **Autorización por rol se valida contra la base de datos, no contra
  el JWT**: `require_roles` lee `usuario.rol.nombre` de un query fresco,
  no del campo `rol` que viene dentro del token. Esto significa que si
  desactivas un usuario o le cambias el rol, sus tokens ya emitidos
  dejan de tener ese permiso en la siguiente request (aunque el JWT en
  sí siga siendo válido hasta que expire).

## Fuera de alcance de este módulo (a propósito)

- Refresh tokens / logout — no se pidió.
- Recuperación de contraseña — no se pidió.
- Restricción por rol dentro de Clientes/Reservaciones/Pagos/Servicios
  (ej. solo admin puede crear Servicios) — no hay regla de negocio
  definida, se deja abierto a cualquier rol autenticado.
- El botón "Authorize" de Swagger espera técnicamente un flujo
  `OAuth2PasswordRequestForm` (form-urlencoded); aquí `/auth/login`
  usa JSON. Funciona para probar con `curl`/Postman/tests, pero el
  botón de Swagger puede no autocompletarse — hay que pegar el token
  manualmente ahí. No se cambió porque no se pidió y JSON es más simple
  para los tests automatizados.

## Cómo correr las pruebas

```bash
pytest tests/test_auth.py -v
# Esperado: 15 passed

pytest tests/ -v
# Esperado: 61 passed (9 clientes + 11 reservaciones + 13 pagos + 13 servicios + 15 auth)
```

## Cómo probarlo a mano

```bash
uvicorn app.main:app --reload
```

1. `python -m scripts.create_admin` (una sola vez, con tu Postgres real).
2. `POST /auth/login` con esas credenciales → copia el `access_token`.
3. Intenta `GET /clientes` sin header → `401`.
4. Repite con `Authorization: Bearer <token>` → `200`.
5. `POST /auth/usuarios` sin ser admin → `403`. Como admin → `200`.
