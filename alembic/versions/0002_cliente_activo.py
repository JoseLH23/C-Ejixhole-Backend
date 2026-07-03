"""agrega columna activo a clientes (soft delete)

Revision ID: 0002_cliente_activo
Revises: a8923b09bb37
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_cliente_activo"
down_revision = "a8923b09bb37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clientes",
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("clientes", "activo")
