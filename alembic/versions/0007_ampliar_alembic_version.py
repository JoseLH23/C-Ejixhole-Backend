"""Hace permanente (para cualquier base de datos nueva) el ancho de
columna que se corrigio a mano en la base real durante AL-04 — la
columna alembic_version.version_num viene por defecto en VARCHAR(32),
insuficiente para nombres de revision descriptivos largos.

revision = "0007_ampliar_alembic_version"
down_revision = "0006_idempotency_keys"
"""
from alembic import op

revision = "0007_ampliar_alembic_version"
down_revision = "0006_idempotency_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64);")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(32);")
