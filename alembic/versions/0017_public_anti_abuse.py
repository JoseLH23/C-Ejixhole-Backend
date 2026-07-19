"""Agrega intentos públicos seudónimos para límites durables.

revision = "0017_public_anti_abuse"
down_revision = "0016_revocable_auth_sessions"
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_public_anti_abuse"
down_revision = "0016_revocable_auth_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_submission_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("contact_hash", sa.String(length=64), nullable=True),
        sa.Column("client_hash", sa.String(length=64), nullable=True),
        sa.Column("nonce_hash", sa.String(length=64), nullable=True),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_public_submission_attempts_ip_hash", "public_submission_attempts", ["ip_hash"])
    op.create_index("ix_public_submission_attempts_contact_hash", "public_submission_attempts", ["contact_hash"])
    op.create_index("ix_public_submission_attempts_client_hash", "public_submission_attempts", ["client_hash"])
    op.create_index("ix_public_submission_attempts_created_at", "public_submission_attempts", ["created_at"])
    op.create_index("ix_public_attempt_ip_created", "public_submission_attempts", ["ip_hash", "created_at"])
    op.create_index("ix_public_attempt_contact_created", "public_submission_attempts", ["contact_hash", "created_at"])
    op.create_index("ix_public_attempt_client_created", "public_submission_attempts", ["client_hash", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_public_attempt_client_created", table_name="public_submission_attempts")
    op.drop_index("ix_public_attempt_contact_created", table_name="public_submission_attempts")
    op.drop_index("ix_public_attempt_ip_created", table_name="public_submission_attempts")
    op.drop_index("ix_public_submission_attempts_created_at", table_name="public_submission_attempts")
    op.drop_index("ix_public_submission_attempts_client_hash", table_name="public_submission_attempts")
    op.drop_index("ix_public_submission_attempts_contact_hash", table_name="public_submission_attempts")
    op.drop_index("ix_public_submission_attempts_ip_hash", table_name="public_submission_attempts")
    op.drop_table("public_submission_attempts")
