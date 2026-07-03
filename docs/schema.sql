-- =====================================================================
-- EjiXhole Experience OS — Schema inicial (Fase 1)
-- PostgreSQL 17
-- =====================================================================
-- Este archivo es la fuente de verdad legible del schema. Los modelos
-- SQLAlchemy en app/models/ deben reflejar exactamente estas tablas.
-- =====================================================================

-- Extensión necesaria para UUID como default de servidor (opcional,
-- se usa PK entero serial por simplicidad y velocidad; UUID se deja
-- como comentario por si se prefiere en el futuro para sync offline).
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================================
-- ROLES
-- =====================================================================
CREATE TABLE roles (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(50) NOT NULL UNIQUE,   -- admin, operador, cajero
    descripcion     VARCHAR(255)
);

-- Roles base del sistema. Se insertan en la migración inicial, no aquí.

-- =====================================================================
-- USUARIOS  (empleados del sistema: admin, recepción, caja)
-- =====================================================================
CREATE TABLE usuarios (
    id                  SERIAL PRIMARY KEY,
    nombre              VARCHAR(120) NOT NULL,
    email               VARCHAR(150) NOT NULL UNIQUE,
    password_hash       VARCHAR(255) NOT NULL,
    rol_id              INTEGER NOT NULL REFERENCES roles(id),
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_usuarios_rol_id ON usuarios(rol_id);

-- =====================================================================
-- CLIENTES
-- =====================================================================
-- Decisión de negocio: duplicate detection dispara sobre telefono O
-- email coincidente. NO se implementa como UNIQUE constraint duro,
-- porque la detección de duplicados es un paso de negocio (alertar /
-- fusionar) y no un rechazo automático de la base de datos — dos
-- personas distintas podrían compartir un teléfono de casa, por
-- ejemplo. Se implementa como índices para que la búsqueda de
-- duplicados sea rápida; la lógica de "es duplicado" vive en la capa
-- de servicios (app/services, próxima fase).
CREATE TABLE clientes (
    id                  SERIAL PRIMARY KEY,
    nombre              VARCHAR(120) NOT NULL,
    apellido            VARCHAR(120),
    telefono            VARCHAR(30),
    email               VARCHAR(150),
    notas               TEXT,
    fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_clientes_telefono ON clientes(telefono);
CREATE INDEX ix_clientes_email ON clientes(email);

-- =====================================================================
-- SERVICIOS  (catálogo de experiencias del parque)
-- =====================================================================
CREATE TABLE servicios (
    id                  SERIAL PRIMARY KEY,
    nombre              VARCHAR(150) NOT NULL,
    descripcion         TEXT,
    precio              NUMERIC(10, 2) NOT NULL CHECK (precio >= 0),
    duracion_minutos    INTEGER,
    capacidad_maxima    INTEGER,
    categoria           VARCHAR(80),
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- RESERVACIONES
-- =====================================================================
-- Decisión de negocio: un cliente solo puede tener UNA reservación
-- activa a la vez ('pendiente' o 'confirmada'). Se implementa como
-- índice único parcial — PostgreSQL lo soporta de forma nativa y es
-- la manera correcta de expresar esta regla a nivel de base de datos
-- (no solo en la capa de aplicación), evitando condiciones de carrera.
--
-- Decisión de negocio: pagos parciales permitidos como anticipo.
-- monto_pagado se mantiene actualizado desde la capa de servicios
-- cada vez que se registra un pago (no es una columna calculada por
-- Postgres, para permitir ajustes manuales como reembolsos parciales).
CREATE TABLE reservaciones (
    id                  SERIAL PRIMARY KEY,
    cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
    servicio_id         INTEGER NOT NULL REFERENCES servicios(id),
    usuario_id          INTEGER NOT NULL REFERENCES usuarios(id),  -- quién la creó
    fecha_reservacion   TIMESTAMPTZ NOT NULL DEFAULT now(),        -- cuándo se hizo la reserva
    fecha_visita        DATE NOT NULL,                             -- cuándo visitan el parque
    num_personas        INTEGER NOT NULL CHECK (num_personas > 0),
    estado              VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                         CHECK (estado IN ('pendiente', 'confirmada', 'completada', 'cancelada')),
    origen              VARCHAR(30) NOT NULL DEFAULT 'recepcion'
                         CHECK (origen IN ('recepcion', 'recepcion_express', 'portal', 'telefono')),
    total               NUMERIC(10, 2) NOT NULL CHECK (total >= 0),
    monto_pagado        NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (monto_pagado >= 0),
    notas               TEXT,
    fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_reservaciones_cliente_id ON reservaciones(cliente_id);
CREATE INDEX ix_reservaciones_servicio_id ON reservaciones(servicio_id);
CREATE INDEX ix_reservaciones_fecha_visita ON reservaciones(fecha_visita);

-- Regla: una reservación activa por cliente (pendiente o confirmada).
CREATE UNIQUE INDEX ux_reservaciones_una_activa_por_cliente
    ON reservaciones (cliente_id)
    WHERE estado IN ('pendiente', 'confirmada');

-- =====================================================================
-- PAGOS
-- =====================================================================
CREATE TABLE pagos (
    id                  SERIAL PRIMARY KEY,
    reservacion_id      INTEGER NOT NULL REFERENCES reservaciones(id),
    usuario_id          INTEGER NOT NULL REFERENCES usuarios(id),  -- quién lo registró
    monto               NUMERIC(10, 2) NOT NULL CHECK (monto > 0),
    tipo                VARCHAR(20) NOT NULL
                         CHECK (tipo IN ('anticipo', 'pago_completo', 'pago_saldo', 'reembolso')),
    metodo_pago         VARCHAR(20) NOT NULL
                         CHECK (metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'otro')),
    referencia          VARCHAR(100),
    notas               TEXT,
    fecha_pago          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_pagos_reservacion_id ON pagos(reservacion_id);

-- =====================================================================
-- CAJA — sesiones (turnos de caja) y movimientos
-- =====================================================================
CREATE TABLE caja_sesiones (
    id                      SERIAL PRIMARY KEY,
    usuario_id              INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_apertura          TIMESTAMPTZ NOT NULL DEFAULT now(),
    monto_apertura          NUMERIC(10, 2) NOT NULL DEFAULT 0,
    fecha_cierre            TIMESTAMPTZ,
    monto_cierre_esperado   NUMERIC(10, 2),
    monto_cierre_real       NUMERIC(10, 2),
    diferencia              NUMERIC(10, 2),
    estado                  VARCHAR(20) NOT NULL DEFAULT 'abierta'
                             CHECK (estado IN ('abierta', 'cerrada')),
    notas                   TEXT
);

-- Regla: un usuario no puede tener dos sesiones de caja abiertas a la vez.
CREATE UNIQUE INDEX ux_caja_sesion_abierta_por_usuario
    ON caja_sesiones (usuario_id)
    WHERE estado = 'abierta';

CREATE TABLE caja_movimientos (
    id                  SERIAL PRIMARY KEY,
    caja_sesion_id      INTEGER NOT NULL REFERENCES caja_sesiones(id),
    pago_id             INTEGER REFERENCES pagos(id),  -- NULL si es un movimiento manual
    tipo                VARCHAR(20) NOT NULL CHECK (tipo IN ('ingreso', 'egreso')),
    monto               NUMERIC(10, 2) NOT NULL CHECK (monto > 0),
    concepto            VARCHAR(255) NOT NULL,
    usuario_id          INTEGER NOT NULL REFERENCES usuarios(id),
    fecha               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_caja_movimientos_sesion_id ON caja_movimientos(caja_sesion_id);

-- =====================================================================
-- CONFIGURACION  (key-value para ajustes del sistema)
-- =====================================================================
CREATE TABLE configuracion (
    id                  SERIAL PRIMARY KEY,
    clave               VARCHAR(100) NOT NULL UNIQUE,
    valor               TEXT,
    descripcion         VARCHAR(255),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =====================================================================
-- RESPALDOS  (registro de backups, no el backup en sí)
-- =====================================================================
CREATE TABLE respaldos (
    id                  SERIAL PRIMARY KEY,
    nombre_archivo      VARCHAR(255) NOT NULL,
    ruta                VARCHAR(500) NOT NULL,
    tamano_bytes        BIGINT,
    tipo                VARCHAR(20) NOT NULL DEFAULT 'manual'
                         CHECK (tipo IN ('manual', 'automatico')),
    estado              VARCHAR(20) NOT NULL DEFAULT 'exitoso'
                         CHECK (estado IN ('exitoso', 'fallido')),
    fecha_creacion      TIMESTAMPTZ NOT NULL DEFAULT now()
);
