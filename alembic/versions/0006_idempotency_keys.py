"""AL-04 (auditoria de seguridad 13/jul/2026): tabla real para
proteger contra doble clic / doble envio en operaciones criticas.

revision = "0006_idempotency_keys"
down_revision = "0005_no_traslape_unidad_hospedaje"
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_idempotency_keys"
down_revision = "0005_no_traslape_unidad_hospedaje"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("clave", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=100), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("clave", "endpoint", name="uq_idempotency_clave_endpoint"),
    )
    op.create_index("ix_idempotency_keys_clave", "idempotency_keys", ["clave"])


def downgrade() -> None:
    op.drop_index("ix_idempotency_keys_clave", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
