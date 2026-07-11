"""portal publico fase 2: usuario_id opcional en reservaciones

Revision ID: 0004_usuario_id_opcional
Revises: 0003_portal_publico_fase1
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa

revision = "0004_usuario_id_opcional"
down_revision = "0003_portal_publico_fase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Las reservaciones del portal público no las crea ningún
    # empleado — usuario_id queda vacío en esos casos.
    op.alter_column("reservaciones", "usuario_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # OJO: si ya existen reservaciones con usuario_id NULL (creadas
    # desde el portal), este downgrade fallará hasta que se les
    # asigne un usuario_id real primero — es esperado, no un bug.
    op.alter_column("reservaciones", "usuario_id", existing_type=sa.Integer(), nullable=False)
