"""CI (hallazgo real 15/jul/2026): en una base de datos nueva desde
cero, la migracion 0005 fallaba con "value too long for type
character varying(32)" — su revision id
("0005_no_traslape_unidad_hospedaje", 33 caracteres) no cabe en la
columna alembic_version.version_num por defecto (VARCHAR(32)), y esa
columna no se ensanchaba a VARCHAR(64) hasta la migracion 0007,
demasiado tarde para la propia 0005.

En la base real (Neon) esto no aplica — ya se corrigio a mano durante
AL-04 (ver 0007), así que esta migracion es un no-op ahi. Se agrega
aqui, ANTES de 0005, solo para que un Postgres nuevo desde cero (CI,
un entorno nuevo) pueda aplicar todo el historial sin tronar. La
migracion 0007 se deja intacta (ensanchar a VARCHAR(64) dos veces no
falla) para no reescribir historial ya aplicado en ningun ambiente.

revision = "0004b_ampliar_alembic_version"
down_revision = "0004_usuario_id_opcional"
"""
from alembic import op

revision = "0004b_ampliar_alembic_version"
down_revision = "0004_usuario_id_opcional"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32);")
