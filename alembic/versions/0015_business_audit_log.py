"""Agrega registro empresarial append-only de auditoría.

revision = "0015_business_audit_log"
down_revision = "0014_outbox_delivery"
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_business_audit_log"
down_revision = "0014_outbox_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(length=220), nullable=True),
        sa.Column("actor_usuario_id", sa.Integer(), nullable=True),
        sa.Column("actor_nombre", sa.String(length=120), nullable=True),
        sa.Column("actor_rol", sa.String(length=50), nullable=True),
        sa.Column("accion", sa.String(length=80), nullable=False),
        sa.Column("entidad_tipo", sa.String(length=80), nullable=False),
        sa.Column("entidad_id", sa.String(length=80), nullable=True),
        sa.Column("origen", sa.String(length=40), server_default="admin", nullable=False),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("antes", sa.JSON(), nullable=True),
        sa.Column("despues", sa.JSON(), nullable=True),
        sa.Column("contexto", sa.JSON(), nullable=True),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_usuario_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", name="uq_audit_events_event_key"),
    )
    op.create_index("ix_audit_events_accion", "audit_events", ["accion"], unique=False)
    op.create_index("ix_audit_events_entidad_tipo", "audit_events", ["entidad_tipo"], unique=False)
    op.create_index("ix_audit_events_entidad_id", "audit_events", ["entidad_id"], unique=False)
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"], unique=False)
    op.create_index("ix_audit_events_fecha_creacion", "audit_events", ["fecha_creacion"], unique=False)
    op.create_index("ix_audit_events_entity", "audit_events", ["entidad_tipo", "entidad_id", "fecha_creacion"], unique=False)
    op.create_index("ix_audit_events_actor_date", "audit_events", ["actor_usuario_id", "fecha_creacion"], unique=False)
    op.create_index("ix_audit_events_action_date", "audit_events", ["accion", "fecha_creacion"], unique=False)

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_events_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events es append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_events_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_events_append_only ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_events_mutation()")
    op.drop_index("ix_audit_events_action_date", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_date", table_name="audit_events")
    op.drop_index("ix_audit_events_entity", table_name="audit_events")
    op.drop_index("ix_audit_events_fecha_creacion", table_name="audit_events")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_entidad_id", table_name="audit_events")
    op.drop_index("ix_audit_events_entidad_tipo", table_name="audit_events")
    op.drop_index("ix_audit_events_accion", table_name="audit_events")
    op.drop_table("audit_events")
