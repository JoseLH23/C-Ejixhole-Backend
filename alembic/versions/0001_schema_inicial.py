"""schema inicial: roles, usuarios, clientes, servicios, reservaciones,
pagos, caja, configuracion, respaldos

Revision ID: 0001_schema_inicial
Revises:
Create Date: 2026-07-03

NOTA: Esta migración fue escrita a mano (no generada con
`alembic revision --autogenerate`) porque el entorno donde se preparó
no tenía acceso a un Postgres real ni a los paquetes instalados. Antes
de aplicarla en tu máquina, corre:

    alembic revision --autogenerate -m "check"

sobre una base de datos vacía y compara el resultado contra este
archivo. Si Alembic no detecta diferencias adicionales, esta migración
es correcta y puedes seguir usándola tal cual.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_schema_inicial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # roles
    # -----------------------------------------------------------------
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=50), nullable=False, unique=True),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
    )

    op.bulk_insert(
        sa.table(
            "roles",
            sa.column("nombre", sa.String),
            sa.column("descripcion", sa.String),
        ),
        [
            {"nombre": "admin", "descripcion": "Acceso total al sistema"},
            {"nombre": "operador", "descripcion": "Recepción, reservaciones y clientes"},
            {"nombre": "cajero", "descripcion": "Caja y pagos"},
        ],
    )

    # -----------------------------------------------------------------
    # usuarios
    # -----------------------------------------------------------------
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("rol_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_usuarios_rol_id", "usuarios", ["rol_id"])

    # -----------------------------------------------------------------
    # clientes
    # -----------------------------------------------------------------
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("apellido", sa.String(length=120), nullable=True),
        sa.Column("telefono", sa.String(length=30), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column(
            "fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_clientes_telefono", "clientes", ["telefono"])
    op.create_index("ix_clientes_email", "clientes", ["email"])

    # -----------------------------------------------------------------
    # servicios
    # -----------------------------------------------------------------
    op.create_table(
        "servicios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("precio", sa.Numeric(10, 2), nullable=False),
        sa.Column("duracion_minutos", sa.Integer(), nullable=True),
        sa.Column("capacidad_maxima", sa.Integer(), nullable=True),
        sa.Column("categoria", sa.String(length=80), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("precio >= 0", name="ck_servicios_precio_positivo"),
    )

    # -----------------------------------------------------------------
    # reservaciones
    # -----------------------------------------------------------------
    op.create_table(
        "reservaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=False),
        sa.Column("servicio_id", sa.Integer(), sa.ForeignKey("servicios.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column(
            "fecha_reservacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("fecha_visita", sa.Date(), nullable=False),
        sa.Column("num_personas", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="pendiente"),
        sa.Column("origen", sa.String(length=30), nullable=False, server_default="recepcion"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("monto_pagado", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column(
            "fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("num_personas > 0", name="ck_reservaciones_num_personas_positivo"),
        sa.CheckConstraint("total >= 0", name="ck_reservaciones_total_positivo"),
        sa.CheckConstraint("monto_pagado >= 0", name="ck_reservaciones_monto_pagado_positivo"),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'confirmada', 'completada', 'cancelada')",
            name="ck_reservaciones_estado_valido",
        ),
        sa.CheckConstraint(
            "origen IN ('recepcion', 'recepcion_express', 'portal', 'telefono')",
            name="ck_reservaciones_origen_valido",
        ),
    )
    op.create_index("ix_reservaciones_cliente_id", "reservaciones", ["cliente_id"])
    op.create_index("ix_reservaciones_servicio_id", "reservaciones", ["servicio_id"])
    op.create_index("ix_reservaciones_fecha_visita", "reservaciones", ["fecha_visita"])

    # Regla de negocio: una reservación activa (pendiente/confirmada) por cliente.
    op.create_index(
        "ux_reservaciones_una_activa_por_cliente",
        "reservaciones",
        ["cliente_id"],
        unique=True,
        postgresql_where=sa.text("estado IN ('pendiente', 'confirmada')"),
    )

    # -----------------------------------------------------------------
    # pagos
    # -----------------------------------------------------------------
    op.create_table(
        "pagos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservacion_id", sa.Integer(), sa.ForeignKey("reservaciones.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("metodo_pago", sa.String(length=20), nullable=False),
        sa.Column("referencia", sa.String(length=100), nullable=True),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column(
            "fecha_pago", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("monto > 0", name="ck_pagos_monto_positivo"),
        sa.CheckConstraint(
            "tipo IN ('anticipo', 'pago_completo', 'pago_saldo', 'reembolso')",
            name="ck_pagos_tipo_valido",
        ),
        sa.CheckConstraint(
            "metodo_pago IN ('efectivo', 'tarjeta', 'transferencia', 'otro')",
            name="ck_pagos_metodo_valido",
        ),
    )
    op.create_index("ix_pagos_reservacion_id", "pagos", ["reservacion_id"])

    # -----------------------------------------------------------------
    # caja_sesiones
    # -----------------------------------------------------------------
    op.create_table(
        "caja_sesiones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column(
            "fecha_apertura",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("monto_apertura", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True),
        sa.Column("monto_cierre_esperado", sa.Numeric(10, 2), nullable=True),
        sa.Column("monto_cierre_real", sa.Numeric(10, 2), nullable=True),
        sa.Column("diferencia", sa.Numeric(10, 2), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="abierta"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.CheckConstraint("estado IN ('abierta', 'cerrada')", name="ck_caja_sesiones_estado_valido"),
    )

    # Regla de negocio: un usuario no puede tener dos sesiones de caja abiertas.
    op.create_index(
        "ux_caja_sesion_abierta_por_usuario",
        "caja_sesiones",
        ["usuario_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'abierta'"),
    )

    # -----------------------------------------------------------------
    # caja_movimientos
    # -----------------------------------------------------------------
    op.create_table(
        "caja_movimientos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "caja_sesion_id", sa.Integer(), sa.ForeignKey("caja_sesiones.id"), nullable=False
        ),
        sa.Column("pago_id", sa.Integer(), sa.ForeignKey("pagos.id"), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("concepto", sa.String(length=255), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("monto > 0", name="ck_caja_movimientos_monto_positivo"),
        sa.CheckConstraint(
            "tipo IN ('ingreso', 'egreso')", name="ck_caja_movimientos_tipo_valido"
        ),
    )
    op.create_index("ix_caja_movimientos_sesion_id", "caja_movimientos", ["caja_sesion_id"])

    # -----------------------------------------------------------------
    # configuracion
    # -----------------------------------------------------------------
    op.create_table(
        "configuracion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clave", sa.String(length=100), nullable=False, unique=True),
        sa.Column("valor", sa.Text(), nullable=True),
        sa.Column("descripcion", sa.String(length=255), nullable=True),
        sa.Column(
            "fecha_actualizacion",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # -----------------------------------------------------------------
    # respaldos
    # -----------------------------------------------------------------
    op.create_table(
        "respaldos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre_archivo", sa.String(length=255), nullable=False),
        sa.Column("ruta", sa.String(length=500), nullable=False),
        sa.Column("tamano_bytes", sa.BigInteger(), nullable=True),
        sa.Column("tipo", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="exitoso"),
        sa.Column(
            "fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("tipo IN ('manual', 'automatico')", name="ck_respaldos_tipo_valido"),
        sa.CheckConstraint(
            "estado IN ('exitoso', 'fallido')", name="ck_respaldos_estado_valido"
        ),
    )


def downgrade() -> None:
    # Orden inverso al de creación, por las llaves foráneas.
    op.drop_table("respaldos")
    op.drop_table("configuracion")
    op.drop_index("ix_caja_movimientos_sesion_id", table_name="caja_movimientos")
    op.drop_table("caja_movimientos")
    op.drop_index("ux_caja_sesion_abierta_por_usuario", table_name="caja_sesiones")
    op.drop_table("caja_sesiones")
    op.drop_index("ix_pagos_reservacion_id", table_name="pagos")
    op.drop_table("pagos")
    op.drop_index("ux_reservaciones_una_activa_por_cliente", table_name="reservaciones")
    op.drop_index("ix_reservaciones_fecha_visita", table_name="reservaciones")
    op.drop_index("ix_reservaciones_servicio_id", table_name="reservaciones")
    op.drop_index("ix_reservaciones_cliente_id", table_name="reservaciones")
    op.drop_table("reservaciones")
    op.drop_table("servicios")
    op.drop_index("ix_clientes_email", table_name="clientes")
    op.drop_index("ix_clientes_telefono", table_name="clientes")
    op.drop_table("clientes")
    op.drop_index("ix_usuarios_rol_id", table_name="usuarios")
    op.drop_table("usuarios")
    op.drop_table("roles")
