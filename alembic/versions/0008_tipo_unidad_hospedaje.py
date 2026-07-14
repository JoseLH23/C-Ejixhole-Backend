"""ME-11 (auditoria de seguridad 13/jul/2026): la categoria/tarifa de
una unidad de hospedaje se derivaba de startswith("Cabañ") sobre el
NOMBRE VISIBLE — renombrar, corregir un acento o traducir cambiaba la
logica de negocio en silencio.

Se agrega tipo_unidad como campo real y estable. El backfill usa la
MISMA regla que el codigo de runtime usaba hasta ahora (startswith) —
es la unica vez que se usa esa regla: aqui, en la migracion, para
convertir datos existentes a la nueva forma estable. A partir de este
commit, el codigo de runtime ya no vuelve a leer el nombre para
decidir nada.

revision = "0008_tipo_unidad_hospedaje"
down_revision = "0007_ampliar_alembic_version"
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_tipo_unidad_hospedaje"
down_revision = "0007_ampliar_alembic_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "unidades_hospedaje",
        sa.Column("tipo_unidad", sa.String(length=20), nullable=False, server_default="habitacion"),
    )
    op.create_check_constraint(
        "ck_unidades_hospedaje_tipo_valido",
        "unidades_hospedaje",
        "tipo_unidad IN ('cabana', 'habitacion')",
    )

    # Backfill único, usando la misma regla que el código de runtime
    # aplicaba hasta ahora — después de esto, el nombre visible ya no
    # decide nada.
    op.execute("UPDATE unidades_hospedaje SET tipo_unidad = 'cabana' WHERE nombre LIKE 'Cabañ%'")

    op.alter_column("unidades_hospedaje", "tipo_unidad", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_unidades_hospedaje_tipo_valido", "unidades_hospedaje", type_="check")
    op.drop_column("unidades_hospedaje", "tipo_unidad")
