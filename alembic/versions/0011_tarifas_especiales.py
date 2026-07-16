"""Agrega reglas de tarifas especiales.

revision = "0011_tarifas_especiales"
down_revision = "0010_bloqueos_por_unidad"
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_tarifas_especiales"
down_revision = "0010_bloqueos_por_unidad"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tarifas_especiales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("porcentaje_ajuste", sa.Numeric(7, 2), nullable=False),
        sa.Column("aplica_a", sa.String(length=20), nullable=False, server_default="todos"),
        sa.Column("dias_semana", sa.JSON(), nullable=True),
        sa.Column("prioridad", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unidad_hospedaje_id", sa.Integer(), sa.ForeignKey("unidades_hospedaje.id", ondelete="CASCADE"), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("fecha_fin >= fecha_inicio", name="ck_tarifas_especiales_rango_valido"),
        sa.CheckConstraint("porcentaje_ajuste >= -100 AND porcentaje_ajuste <= 500", name="ck_tarifas_especiales_porcentaje_valido"),
        sa.CheckConstraint("aplica_a IN ('todos','entrada','camping','hospedaje')", name="ck_tarifas_especiales_aplica_a_valido"),
    )
    op.create_index("ix_tarifas_especiales_fecha_inicio", "tarifas_especiales", ["fecha_inicio"])
    op.create_index("ix_tarifas_especiales_fecha_fin", "tarifas_especiales", ["fecha_fin"])


def downgrade() -> None:
    op.drop_index("ix_tarifas_especiales_fecha_fin", table_name="tarifas_especiales")
    op.drop_index("ix_tarifas_especiales_fecha_inicio", table_name="tarifas_especiales")
    op.drop_table("tarifas_especiales")
