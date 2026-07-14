"""CR-02 (auditoria de seguridad 13/jul/2026): restriccion real a
nivel de base de datos contra doble reservacion por condicion de
carrera.

Antes de esto, la disponibilidad se validaba solo en la capa de
aplicacion (leer -> validar -> insertar), sin ninguna proteccion
transaccional real: dos solicitudes simultaneas podian leer la unidad
como libre y ambas confirmar la misma cabana/habitacion.

Se agrega una restriccion EXCLUDE USING gist real de PostgreSQL:
ninguna unidad de hospedaje puede tener dos reservaciones activas
(pendiente/confirmada) con rangos de fecha que se traslapen. Esto lo
garantiza el motor de base de datos, no la aplicacion — es imposible
de burlar con una condicion de carrera.

revision = "0005_no_traslape_unidad_hospedaje"
down_revision = "0004_usuario_id_opcional"
"""
from alembic import op

revision = "0005_no_traslape_unidad_hospedaje"
down_revision = "0004_usuario_id_opcional"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # btree_gist es necesario para poder combinar en el mismo EXCLUDE
    # una columna de igualdad normal (unidad_hospedaje_id, entero) con
    # una de rango (daterange) usando el mismo indice GiST.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")

    op.execute(
        """
        ALTER TABLE reservaciones
        ADD CONSTRAINT ck_no_traslape_unidad_hospedaje
        EXCLUDE USING gist (
            unidad_hospedaje_id WITH =,
            daterange(fecha_llegada, fecha_salida, '[)') WITH &&
        )
        WHERE (
            unidad_hospedaje_id IS NOT NULL
            AND estado IN ('pendiente', 'confirmada')
        );
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE reservaciones DROP CONSTRAINT IF EXISTS ck_no_traslape_unidad_hospedaje;")
    # No se quita la extension btree_gist en el downgrade — podría
    # estar en uso por otra cosa; quitarla es una decisión manual.
