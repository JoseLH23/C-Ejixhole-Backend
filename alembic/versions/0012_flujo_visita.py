"""Agrega check-in, check-out y estado operativo en curso.

revision = "0012_flujo_visita"
down_revision = "0011_tarifas_especiales"
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_flujo_visita"
down_revision = "0011_tarifas_especiales"
branch_labels = None
depends_on = None


_ESTADOS_NUEVOS = "('pendiente', 'confirmada', 'en_curso', 'completada', 'cancelada')"
_ESTADOS_ANTERIORES = "('pendiente', 'confirmada', 'completada', 'cancelada')"


def _crear_exclusion(estados: str) -> None:
    op.execute(
        f"""
        ALTER TABLE reservaciones
        ADD CONSTRAINT ck_no_traslape_unidad_hospedaje
        EXCLUDE USING gist (
            unidad_hospedaje_id WITH =,
            daterange(fecha_llegada, fecha_salida, '[)') WITH &&
        )
        WHERE (
            unidad_hospedaje_id IS NOT NULL
            AND estado IN {estados}
        );
        """
    )


def _eliminar_exclusion() -> None:
    op.execute(
        "ALTER TABLE reservaciones "
        "DROP CONSTRAINT IF EXISTS ck_no_traslape_unidad_hospedaje;"
    )


def upgrade() -> None:
    op.add_column(
        "reservaciones", sa.Column("fecha_checkin", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "reservaciones", sa.Column("checkin_usuario_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "reservaciones", sa.Column("fecha_checkout", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "reservaciones", sa.Column("checkout_usuario_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_reservaciones_checkin_usuario",
        "reservaciones",
        "usuarios",
        ["checkin_usuario_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_reservaciones_checkout_usuario",
        "reservaciones",
        "usuarios",
        ["checkout_usuario_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        """
        UPDATE reservaciones
        SET fecha_checkin = COALESCE(fecha_checkin, fecha_actualizacion),
            fecha_checkout = COALESCE(fecha_checkout, fecha_actualizacion),
            checkin_usuario_id = COALESCE(checkin_usuario_id, usuario_id),
            checkout_usuario_id = COALESCE(checkout_usuario_id, usuario_id)
        WHERE estado = 'completada';
        """
    )

    _eliminar_exclusion()
    op.drop_constraint("ck_reservaciones_estado_valido", "reservaciones", type_="check")
    op.create_check_constraint(
        "ck_reservaciones_estado_valido",
        "reservaciones",
        f"estado IN {_ESTADOS_NUEVOS}",
    )
    _crear_exclusion("('pendiente', 'confirmada', 'en_curso')")


def downgrade() -> None:
    op.execute("UPDATE reservaciones SET estado = 'confirmada' WHERE estado = 'en_curso';")

    _eliminar_exclusion()
    op.drop_constraint("ck_reservaciones_estado_valido", "reservaciones", type_="check")
    op.create_check_constraint(
        "ck_reservaciones_estado_valido",
        "reservaciones",
        f"estado IN {_ESTADOS_ANTERIORES}",
    )
    _crear_exclusion("('pendiente', 'confirmada')")

    op.drop_constraint("fk_reservaciones_checkout_usuario", "reservaciones", type_="foreignkey")
    op.drop_constraint("fk_reservaciones_checkin_usuario", "reservaciones", type_="foreignkey")
    op.drop_column("reservaciones", "checkout_usuario_id")
    op.drop_column("reservaciones", "fecha_checkout")
    op.drop_column("reservaciones", "checkin_usuario_id")
    op.drop_column("reservaciones", "fecha_checkin")
