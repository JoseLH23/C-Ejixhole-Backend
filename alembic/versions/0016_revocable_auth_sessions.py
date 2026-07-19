"""Agrega sesiones administrativas revocables.

revision = "0016_revocable_auth_sessions"
down_revision = "0015_business_audit_log"
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_revocable_auth_sessions"
down_revision = "0015_business_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jti", sa.String(length=36), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_sessions_jti", "auth_sessions", ["jti"], unique=True)
    op.create_index("ix_auth_sessions_usuario_id", "auth_sessions", ["usuario_id"], unique=False)
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"], unique=False)
    op.create_index("ix_auth_sessions_revoked_at", "auth_sessions", ["revoked_at"], unique=False)
    op.create_index(
        "ix_auth_sessions_usuario_activa",
        "auth_sessions",
        ["usuario_id", "revoked_at", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_auth_sessions_usuario_activa", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_revoked_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_usuario_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_jti", table_name="auth_sessions")
    op.drop_table("auth_sessions")
