"""ME-11 (auditoria de seguridad 13/jul/2026), reincidencia detectada
15/jul/2026: _resolver_servicio_id (app/services/publico_service.py)
elegia entre el servicio "Cabañas" y "Habitaciones" filtrando por
Servicio.nombre — el mismo texto libre que el modulo Servicios deja
editar al staff. Renombrar cualquiera de los dos rompia en silencio
la creacion de reservaciones de hospedaje.

Mismo patron que la migracion 0008 uso para UnidadHospedaje.tipo_unidad:
se agrega tipo_unidad_hospedaje como campo real y estable, NULL para
cualquier servicio que no sea de categoria "hospedaje". El backfill
usa la MISMA regla que el codigo de runtime usaba hasta ahora (nombre
exacto) — es la unica vez que se usa esa regla: aqui, para convertir
datos existentes a la forma estable. A partir de este commit, el
codigo de runtime ya no vuelve a leer el nombre para decidir nada.

revision = "0009_servicio_tipo_hospedaje"
down_revision = "0008_tipo_unidad_hospedaje"
"""
import sqlalchemy as sa
from alembic import op

revision = "0009_servicio_tipo_hospedaje"
down_revision = "0008_tipo_unidad_hospedaje"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "servicios",
        sa.Column("tipo_unidad_hospedaje", sa.String(length=20), nullable=True),
    )
    op.create_check_constraint(
        "ck_servicios_tipo_unidad_hospedaje_valido",
        "servicios",
        "tipo_unidad_hospedaje IN ('cabana', 'habitacion') OR tipo_unidad_hospedaje IS NULL",
    )

    # Backfill único, usando la misma regla que el código de runtime
    # aplicaba hasta ahora — después de esto, el nombre visible ya no
    # decide nada.
    op.execute(
        "UPDATE servicios SET tipo_unidad_hospedaje = 'cabana' "
        "WHERE nombre = 'Cabañas' AND categoria = 'hospedaje'"
    )
    op.execute(
        "UPDATE servicios SET tipo_unidad_hospedaje = 'habitacion' "
        "WHERE nombre = 'Habitaciones' AND categoria = 'hospedaje'"
    )


def downgrade() -> None:
    op.drop_constraint("ck_servicios_tipo_unidad_hospedaje_valido", "servicios", type_="check")
    op.drop_column("servicios", "tipo_unidad_hospedaje")
