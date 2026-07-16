"""Eventos de dominio pendientes de entrega a integraciones externas."""
from __future__ import annotations

import uuid

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Integer, String, Text, UniqueConstraint, func

from app.database import Base


OUTBOX_STATUSES = ("pending", "published", "failed")


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_outbox_events_event_key"),
        CheckConstraint(
            "status IN ('pending', 'published', 'failed')",
            name="ck_outbox_events_status",
        ),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_key = Column(String(160), nullable=False)
    event_type = Column(String(80), nullable=False, index=True)
    aggregate_type = Column(String(50), nullable=False)
    aggregate_id = Column(String(64), nullable=False, index=True)
    schema_version = Column(Integer, nullable=False, default=1, server_default="1")
    payload = Column(JSON, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    available_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
