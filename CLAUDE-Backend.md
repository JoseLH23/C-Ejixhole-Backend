# CLAUDE.md — Ejixhole Backend

Contexto persistente para Claude Code en este repo. Léelo completo antes de tocar código.

## Qué es esto

Backend real de **EjiXhole**, un parque ecoturístico real (El Naranjo, S.L.P., México, fundado por la familia del dueño en tierra ejidal). FastAPI + PostgreSQL (Neon en producción, SQLite en memoria para tests) + SQLAlchemy + Alembic. Desplegado en Render.

Consumido por dos frontends reales, en repos separados:
- `ejixhole-frontend` — panel administrativo interno (staff).
- `ejixhole-reservas` — portal público de reservaciones (visitantes, sin login).

## Entorno — LEE ESTO PRIMERO

- **Windows + PowerShell**, no bash/CMD. Nunca sugieras `export X=y` — es `$env:X = "y"`.
- venv en `.\venv`. Activar: `.\venv\Scripts\Activate.ps1` (si PowerShell bloquea el script: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, una sola vez).
- **Guarda SIEMPRE los archivos en UTF-8 sin BOM.** Ya hubo un incidente real: `requirements.txt` terminó en UTF-16 (probablemente por cómo algún editor/PowerShell lo guardó) y rompió `pip install` en silencio durante semanas antes de que se detectara. Si vas a generar un archivo nuevo, confírmalo.
- Python 3.11.

## Comandos reales

```powershell
pip install -r requirements.txt -r requirements-dev.txt   # runtime + dev (pytest) separados, a propósito (BA-04)
alembic upgrade head                                       # aplicar migraciones a la BD real
$env:PYTHONPATH = "."
pytest -q                                                   # suite completo (225+ tests, SQLite en memoria)
uvicorn app.main:app --reload
```

## Arquitectura — Clean Architecture estricta, no la rompas

```
app/models/       SQLAlchemy — la fuente de verdad de la base de datos
app/schemas/       Pydantic — entrada/salida de la API, NUNCA el modelo de BD directo
app/repositories/  Acceso a datos puro — sin lógica de negocio
app/services/       Lógica de negocio — aquí van las reglas reales
app/routes/         FastAPI routers — casi sin lógica, delegan a services
app/core/           config.py, security.py, idempotency.py, rate_limiter.py
```

Nunca mezcles acceso a datos con lógica de negocio. Un repository no debe lanzar `HTTPException` (eso es de la capa de service/route).

## Convenciones reales que ya existen — sigue el patrón, no inventes uno nuevo

- **Auth real por JWT + rol.** Casi todos los routers tienen `dependencies=[Depends(require_roles("admin", ...))]` a nivel de router. Solo `publico_routes.py` es intencionalmente público.
- **`usuario_id` NUNCA se acepta del body del cliente.** Se deriva siempre de `Depends(require_roles(...))` → `usuario_actual.id`. Esto fue un hallazgo real de seguridad (AL-01) — si ves un schema con `usuario_id: int` como campo de entrada, es un bug, repórtalo, no lo repliques.
- **Idempotencia real** (`app/core/idempotency.py`, `ejecutar_con_idempotencia`) en las operaciones que crean/mutan dinero o reservaciones (crear reservación, registrar pago, caja). Patrón "reservar primero" (tabla `idempotency_keys`, constraint único) — no un simple chequeo antes de escribir, eso no cierra la condición de carrera real.
- **Rate limiting real** (`app/core/rate_limiter.py`) en `/auth/login` y en todas las rutas de `/publico/*`.
- **Fail-fast, nunca fail-open.** `JWT_SECRET_KEY` sin configurar → la app NO arranca (ver `app/core/config.py`). Mismo criterio para cualquier config nueva que sea de seguridad: si falta, truena con un mensaje claro, nunca cae a un default inseguro.
- **`ENVIRONMENT`** controla si `/docs`/`/redoc`/`/openapi.json` están visibles — default `"production"` (ocultos). Para verlos en desarrollo local: `ENVIRONMENT=development` en tu `.env`.
- **Pydantic v2 real**: `model_config = ConfigDict(from_attributes=True)`, nunca `class Config:` (estilo v1, ya migrado por completo).
- **Reglas de negocio nunca dependen de texto visible.** Hallazgo real (ME-11): la categoría de una unidad de hospedaje se calculaba con `nombre.startswith("Cabañ")` — renombrar rompía la lógica en silencio. Ahora es `tipo_unidad` (columna real, con constraint). Si ves lógica de negocio leyendo un campo de texto libre/nombre, sospecha.
- **Migraciones Alembic**: nombres de revisión cortos — ya hubo un incidente real donde un nombre de 34 caracteres superó el límite de `alembic_version.version_num` (VARCHAR(32) por defecto; ya se amplió a 64 en la migración `0007`, pero sé conservador con nombres nuevos de todas formas).

## Testing

- Todos los tests usan **SQLite en memoria** (`create_engine("sqlite:///:memory:")`), nunca Postgres real — así que ninguna restricción específica de Postgres (como `EXCLUDE USING gist`) se puede probar de punta a punta ahí; para esas, documenta la limitación en el test en vez de fingir que se probó.
- `conftest.py` en la raíz fija `JWT_SECRET_KEY` y `ENVIRONMENT` de prueba antes de que se importe `app` — necesario porque `app/core/config.py` falla si faltan.
- Patrón de fixture típico: `db_session` (engine SQLite fresco) + `client` (TestClient con override de `get_db`) + fixtures de catálogo (`setup_basico`, `setup_hospedaje`, `catalogo`) según el archivo.
- Si agregas un test que golpea rutas reales por HTTP, revisa si necesita headers de auth (`Authorization: Bearer <token>`) — la mayoría de las rutas los requieren.

## Auditoría de seguridad — julio 2026

Hubo una auditoría profesional completa (40 hallazgos). La mayoría de los críticos/altos ya están resueltos con evidencia real (tests + verificación en producción, no solo "debería funcionar"). Si encuentras un comentario que dice `CR-XX`, `AL-XX`, `ME-XX` o `BA-XX` en el código, es una referencia a esa auditoría — no lo borres sin entender por qué existe.

Pendiente real, no resuelto (no es negligencia, requiere más que una sesión de código):
- JWT del frontend en `localStorage` (debería ser cookie httpOnly) — cambio de arquitectura, no un parche.
- CI/CD completo, SAST/SBOM, tests de frontend — necesitan decisión de herramienta antes de instalar algo.
- Observabilidad, backups probados, gobierno de datos — política/infraestructura, no código.

## Reglas de trabajo

1. Nunca asumas el contenido de un archivo que no has leído en esta sesión — pídelo o léelo primero.
2. Nunca borres una funcionalidad existente sin decir explícitamente qué y por qué.
3. Antes de un cambio de arquitectura, explica la alternativa y por qué es mejor — no la apliques en silencio.
4. Corre `pytest -q` completo después de cualquier cambio, no solo el archivo que tocaste.
5. Si un cambio requiere una migración de Alembic, créala — nunca alteres el modelo de SQLAlchemy sin la migración correspondiente.
