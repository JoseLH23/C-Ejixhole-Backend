"""Permite bloqueos operativos por unidad de hospedaje.

revision = "0010_bloqueos_por_unidad"
down_revision = "0009_eventos_calendario"
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_bloqueos_por_unidad"
down_revision = "0009_eventos_calendario"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "eventos_calendario",
        sa.Column("unidad_hospedaje_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_eventos_calendario_unidad_hospedaje",
        "eventos_calendario",
        "unidades_hospedaje",
        ["unidad_hospedaje_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_eventos_calendario_unidad_hospedaje_id",
        "eventos_calendario",
        ["unidad_hospedaje_id"],
    )
    op.create_check_constraint(
        "ck_eventos_calendario_unidad_solo_bloqueo",
        "eventos_calendario",
        "unidad_hospedaje_id IS NULL OR tipo = 'bloqueo'",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_eventos_calendario_unidad_solo_bloqueo",
        "eventos_calendario",
        type_="check",
    )
    op.drop_index(
        "ix_eventos_calendario_unidad_hospedaje_id",
        table_name="eventos_calendario",
    )
    op.drop_constraint(
        "fk_eventos_calendario_unidad_hospedaje",
        "eventos_calendario",
        type_="foreignkey",
    )
    op.drop_column("eventos_calendario", "unidad_hospedaje_id")
