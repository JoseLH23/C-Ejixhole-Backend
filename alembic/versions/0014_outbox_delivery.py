"""Agrega bloqueo, reintentos y dead-letter al outbox.

revision = "0014_outbox_delivery"
down_revision = "0013_domain_events_outbox"
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_outbox_delivery"
down_revision = "0013_domain_events_outbox"
branch_labels = None
depends_on = None


_NEW_STATUSES = "('pending', 'processing', 'published', 'failed', 'dead_letter')"
_OLD_STATUSES = "('pending', 'published', 'failed')"


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("locked_by", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("last_http_status", sa.Integer(), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("last_response", sa.Text(), nullable=True),
    )

    op.drop_constraint("ck_outbox_events_status", "outbox_events", type_="check")
    op.create_check_constraint(
        "ck_outbox_events_status",
        "outbox_events",
        f"status IN {_NEW_STATUSES}",
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE outbox_events
        SET status = 'failed',
            locked_at = NULL,
            locked_by = NULL,
            dead_lettered_at = NULL
        WHERE status IN ('processing', 'dead_letter');
        """
    )
    op.drop_constraint("ck_outbox_events_status", "outbox_events", type_="check")
    op.create_check_constraint(
        "ck_outbox_events_status",
        "outbox_events",
        f"status IN {_OLD_STATUSES}",
    )

    op.drop_column("outbox_events", "last_response")
    op.drop_column("outbox_events", "last_http_status")
    op.drop_column("outbox_events", "locked_by")
    op.drop_column("outbox_events", "locked_at")
    op.drop_column("outbox_events", "dead_lettered_at")
