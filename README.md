# EjiXhole Experience OS — Backend

API principal del ecosistema EjiXhole. Administra la operación interna y
expone los endpoints públicos utilizados por el portal de reservaciones.

## Estado

Proyecto en **preproducción**. El núcleo de negocio ya funciona y actualmente
se encuentra en etapa de estabilización, pruebas integrales y preparación
operativa.

## Tecnologías

- Python 3.11+
- FastAPI
- PostgreSQL
- SQLAlchemy 2
- Alembic
- Pydantic 2
- JWT
- Pytest
- Resend

## Módulos disponibles

- Autenticación y permisos por rol
- Usuarios
- Clientes
- Servicios
- Reservaciones
- Pagos
- Caja
- Dashboard
- Reportes
- Portal público de reservaciones
- Notificaciones por correo

## Arquitectura

```text
app/
├── core/          configuración, seguridad y utilidades
├── models/        modelos SQLAlchemy
├── schemas/       contratos de entrada y salida
├── repositories/  acceso a datos
├── services/      reglas de negocio
└── routes/        endpoints FastAPI
```

Las reglas de negocio permanecen en `services/`; las rutas coordinan las
peticiones y los repositorios aíslan el acceso a PostgreSQL.

## Seguridad implementada

- Autenticación JWT
- Permisos por rol
- Rutas internas protegidas
- Límite de intentos de inicio de sesión
- Límite de solicitudes en endpoints públicos
- CORS restringido a los clientes autorizados
- Límites de paginación
- Clave JWT obligatoria y sin valor inseguro por defecto
- Restricción PostgreSQL contra traslapes simultáneos de hospedaje

## Instalación local

```powershell
git clone https://github.com/JoseLH23/C-Ejixhole-Backend.git
cd C-Ejixhole-Backend

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
Copy-Item .env.example .env
```

Configura como mínimo:

```env
DATABASE_URL=postgresql+psycopg2://usuario:password@localhost:5432/ejixhole_db
JWT_SECRET_KEY=una-clave-segura-de-al-menos-32-caracteres
JWT_EXPIRE_MINUTES=60
```

Para las notificaciones por correo:

```env
RESEND_API_KEY=
RESEND_FROM_EMAIL=onboarding@resend.dev
NOTIFICACIONES_EMAIL_DESTINO=
```

## Base de datos

Aplica las migraciones:

```powershell
alembic upgrade head
```

Carga el catálogo público cuando corresponda:

```powershell
python -m scripts.seed_catalogo_publico
```

Crea el primer administrador:

```powershell
python -m scripts.create_admin
```

## Ejecutar la API

```powershell
uvicorn app.main:app --reload
```

Direcciones locales:

- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Estado: `http://127.0.0.1:8000/status`

## Despliegue en Render Free

El plan gratuito no ofrece Shell. Para evitar que producción quede atrasada
respecto al código, utiliza este **Start Command**:

```text
python -m scripts.start_render
```

Ese módulo ejecuta primero `alembic upgrade head` y solo inicia Uvicorn cuando
la migración termina correctamente. Si Alembic falla, el despliegue también
falla y la API no arranca con un esquema incompleto.

No combines este comando con `downgrade`, `drop`, `reset` ni creación manual de
tablas. Alembic sigue siendo la única fuente de verdad del esquema.

## Pruebas

```powershell
pytest -q
```

Las pruebas cubren autenticación, clientes, servicios, reservaciones, pagos,
caja, dashboard, reportes, usuarios y portal público.

## Aplicaciones consumidoras

- `ejixhole-frontend`: panel administrativo
- `ejixhole-reservas`: sitio público y flujo de reservación

## Próximos objetivos

1. Automatizar pruebas con GitHub Actions.
2. Verificar respaldo y restauración de PostgreSQL.
3. Añadir monitoreo y logs estructurados.
4. Ejecutar una reservación completa de extremo a extremo.
5. Versionar la API antes de conectar MH-Core.
6. Integrar MH-Core mediante APIs y eventos, nunca mediante acceso directo
   a esta base de datos.

## Documentación del ecosistema

La visión, arquitectura y roadmap general se mantienen en el repositorio
privado `MH-Ecosystem`.
