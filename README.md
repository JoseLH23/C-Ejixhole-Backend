# EjiXhole Experience OS — Backend (Fase 1: Schema)

## Qué hay aquí

- `docs/schema.sql` — el schema completo en SQL puro, con comentarios
  explicando cada decisión de negocio. Léelo primero si quieres
  entender el diseño sin tocar Python.
- `app/models/` — los mismos modelos, en SQLAlchemy 2.0.
- `alembic/versions/0001_schema_inicial.py` — migración inicial escrita
  a mano (ver nota importante abajo).
- `app/database.py`, `app/core/config.py` — conexión y configuración.

## Tablas incluidas en esta fase

`roles`, `usuarios`, `clientes`, `servicios`, `reservaciones`, `pagos`,
`caja_sesiones`, `caja_movimientos`, `configuracion`, `respaldos`.

**No incluidas todavía** (a propósito, no por falta de tiempo):
Dashboard y Reportes no necesitan tabla propia (son consultas sobre
las tablas de arriba). Diagnóstico es logging de aplicación. Portal
reutiliza `usuarios` con un rol de cliente. Recepción Express reutiliza
la tabla `reservaciones` con `origen = 'recepcion_express'`.

## Reglas de negocio ya en el schema

1. **Un cliente, una reservación activa a la vez** → índice único
   parcial en `reservaciones (cliente_id) WHERE estado IN ('pendiente','confirmada')`.
2. **Pagos parciales como anticipo** → `reservaciones.total` y
   `reservaciones.monto_pagado` son columnas separadas; `pagos.tipo`
   distingue `anticipo` / `pago_completo` / `pago_saldo` / `reembolso`.
   El saldo se calcula en Python (`Reservacion.saldo_pendiente`), no en
   la base de datos, para poder ajustar manualmente si hay reembolsos.
3. **Detección de duplicados por teléfono o email** → son índices
   normales (no UNIQUE), porque la detección es una decisión de
   negocio (alertar/fusionar), no un rechazo automático de la BD. La
   lógica real de "esto es un duplicado" va en la capa de servicios,
   que aún no existe (siguiente fase).

## Cómo correrlo en tu máquina

Ya tienes PostgreSQL 17, pgAdmin y Python 3.11+ instalados, así que:

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # si usaras Mac/Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear la base de datos y el usuario en Postgres (una vez, desde psql o pgAdmin)
#    CREATE DATABASE ejixhole_db;
#    CREATE USER ejixhole_user WITH PASSWORD 'changeme';
#    GRANT ALL PRIVILEGES ON DATABASE ejixhole_db TO ejixhole_user;

# 4. Configurar variables de entorno
copy .env.example .env         # Windows
# cp .env.example .env         # Mac/Linux
# edita .env con tu contraseña real

# 5. Aplicar la migración
alembic upgrade head
```

## ⚠️ Importante sobre la migración inicial

`0001_schema_inicial.py` la escribí a mano porque el entorno donde
preparé esto no tenía acceso a internet para instalar SQLAlchemy,
Alembic o psycopg2 — así que no pude ejecutar `alembic revision
--autogenerate` ni correrla contra un Postgres real. Validé:

- Que los archivos Python compilan sin errores de sintaxis
  (`python -m py_compile`).
- Que cada modelo en `app/models/` coincide campo por campo con
  `docs/schema.sql` y con la migración.

Lo que **no pude validar** porque no tuve Postgres a la mano: que la
migración corra sin errores contra una base real, y que Alembic no
detecte diferencias entre los modelos y las tablas creadas.

Antes de construir nada encima de esto, por favor corre:

```bash
alembic upgrade head
alembic revision --autogenerate -m "check"
```

Si el segundo comando genera una migración vacía (`pass` en upgrade y
downgrade), todo coincide y puedes borrar ese archivo de check y
seguir. Si detecta diferencias, avísame qué encontró y lo ajustamos —
es más rápido corregir un detalle puntual que yo adivinando en un
entorno sin base de datos.

## Siguiente paso sugerido

Una vez confirmado que la migración corre limpio: capa de servicios
(`app/services/`) con la lógica de detección de duplicados y
actualización de `monto_pagado`, y capa de rutas FastAPI
(`app/routes/`) con JWT.
