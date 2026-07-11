"""portal publico fase 1: unidades de hospedaje, tipo/fechas de reservacion, servicios reservables

Revision ID: 0003_portal_publico_fase1
Revises: 0002_cliente_activo
Create Date: 2026-07-05

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_portal_publico_fase1"
down_revision = "0002_cliente_activo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Tabla nueva: unidades de hospedaje individuales (Habitación 1,
    #    Habitación 2, Cabaña 1). Camping no entra aquí — no tiene
    #    límite ni necesita disponibilidad.
    op.create_table(
        "unidades_hospedaje",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=100), nullable=False, unique=True),
        sa.Column("capacidad_maxima", sa.Integer(), nullable=False),
        sa.Column("precio_por_noche", sa.Numeric(10, 2), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("capacidad_maxima > 0", name="ck_unidades_hospedaje_capacidad_positiva"),
        sa.CheckConstraint("precio_por_noche >= 0", name="ck_unidades_hospedaje_precio_positivo"),
    )

    # 2) Campo nuevo en servicios: distingue lo reservable/pagable en el
    #    portal de lo que solo es catálogo informativo.
    op.add_column(
        "servicios",
        sa.Column("reservable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # 3) Campos nuevos en reservaciones.
    op.add_column("reservaciones", sa.Column("fecha_llegada", sa.Date(), nullable=True))
    op.add_column("reservaciones", sa.Column("fecha_salida", sa.Date(), nullable=True))
    op.add_column(
        "reservaciones",
        sa.Column("tipo_reservacion", sa.String(length=20), nullable=False, server_default="entrada"),
    )
    op.add_column(
        "reservaciones", sa.Column("unidad_hospedaje_id", sa.Integer(), nullable=True)
    )
    op.create_index("ix_reservaciones_fecha_llegada", "reservaciones", ["fecha_llegada"])
    op.create_index(
        "ix_reservaciones_unidad_hospedaje_id", "reservaciones", ["unidad_hospedaje_id"]
    )
    op.create_foreign_key(
        "fk_reservaciones_unidad_hospedaje_id",
        "reservaciones",
        "unidades_hospedaje",
        ["unidad_hospedaje_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_reservaciones_tipo_valido",
        "reservaciones",
        "tipo_reservacion IN ('entrada', 'camping', 'hospedaje')",
    )

    # 4) Se quita la regla "un cliente, una reservación activa a la vez"
    #    — decisión explícita del negocio (ver docs/portal-publico-fase-1.md):
    #    con el portal público, un cliente debe poder tener varias
    #    reservaciones activas simultáneas.
    op.drop_index("ux_reservaciones_una_activa_por_cliente", table_name="reservaciones")


def downgrade() -> None:
    op.create_index(
        "ux_reservaciones_una_activa_por_cliente",
        "reservaciones",
        ["cliente_id"],
        unique=True,
        postgresql_where=sa.text("estado IN ('pendiente', 'confirmada')"),
        sqlite_where=sa.text("estado IN ('pendiente', 'confirmada')"),
    )

    op.drop_constraint("ck_reservaciones_tipo_valido", "reservaciones", type_="check")
    op.drop_constraint("fk_reservaciones_unidad_hospedaje_id", "reservaciones", type_="foreignkey")
    op.drop_index("ix_reservaciones_unidad_hospedaje_id", table_name="reservaciones")
    op.drop_index("ix_reservaciones_fecha_llegada", table_name="reservaciones")
    op.drop_column("reservaciones", "unidad_hospedaje_id")
    op.drop_column("reservaciones", "tipo_reservacion")
    op.drop_column("reservaciones", "fecha_salida")
    op.drop_column("reservaciones", "fecha_llegada")

    op.drop_column("servicios", "reservable")

    op.drop_table("unidades_hospedaje")
