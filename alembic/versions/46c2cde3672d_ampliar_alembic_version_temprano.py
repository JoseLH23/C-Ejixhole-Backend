"""ampliar alembic_version temprano

Revision ID: 46c2cde3672d
Revises: 0001_schema_inicial
Create Date: 2026-07-15 00:00:00.000000

Empalmada justo despues de 0001 (antes de 'a8923b09bb37' / 0002) para
adelantar el ALTER que ya hacia 0007_ampliar_alembic_version. En una
base de datos nueva, la cadena original llegaba a la revision
"0005_no_traslape_unidad_hospedaje" (34 caracteres) con
alembic_version.version_num todavia en VARCHAR(32) por defecto -- el
INSERT/UPDATE del propio alembic fallaba con
StringDataRightTruncation antes de llegar a 0007. En produccion nunca
se noto porque la columna se amplio a mano (ver 0007). No se renombra
ninguna revision existente -- 0007 se deja igual y simplemente vuelve
a ejecutar el mismo ALTER (no-op) para bases que ya pasaron por aqui.
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "46c2cde3672d"
down_revision = "0001_schema_inicial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")


def downgrade() -> None:
    # El ancho de la tabla de control es infraestructura de Alembic, no
    # una regla de negocio de esta revision. Reducirlo a 32 rompe el
    # propio rollback cuando Alembic intenta registrar revisiones largas
    # ya presentes en el historial. Se conserva VARCHAR(64) de forma
    # intencional y segura en bases nuevas y existentes.
    pass
