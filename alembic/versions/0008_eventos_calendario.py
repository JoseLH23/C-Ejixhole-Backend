"""Agrega eventos internos compartidos del calendario operativo.

revision = "0008_eventos_calendario"
down_revision = "0007_ampliar_alembic_version"
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_eventos_calendario"
down_revision = "0007_ampliar_alembic_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eventos_calendario",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.String(length=120), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=False),
        sa.Column("fecha_fin", sa.Date(), nullable=False),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "tipo IN ('bloqueo', 'mantenimiento', 'recordatorio', 'campana')",
            name="ck_eventos_calendario_tipo_valido",
        ),
        sa.CheckConstraint("fecha_fin >= fecha_inicio", name="ck_eventos_calendario_rango_valido"),
    )
    op.create_index("ix_eventos_calendario_fecha_inicio", "eventos_calendario", ["fecha_inicio"])
    op.create_index("ix_eventos_calendario_fecha_fin", "eventos_calendario", ["fecha_fin"])


def downgrade() -> None:
    op.drop_index("ix_eventos_calendario_fecha_fin", table_name="eventos_calendario")
    op.drop_index("ix_eventos_calendario_fecha_inicio", table_name="eventos_calendario")
    op.drop_table("eventos_calendario")
