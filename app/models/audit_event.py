"""Registro append-only de acciones administrativas y operativas."""
from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_audit_events_event_key"),
        Index("ix_audit_events_entity", "entidad_tipo", "entidad_id", "fecha_creacion"),
        Index("ix_audit_events_actor_date", "actor_usuario_id", "fecha_creacion"),
        Index("ix_audit_events_action_date", "accion", "fecha_creacion"),
    )

    id = Column(Integer, primary_key=True)
    event_key = Column(String(220), nullable=True)
    actor_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    actor_nombre = Column(String(120), nullable=True)
    actor_rol = Column(String(50), nullable=True)
    accion = Column(String(80), nullable=False, index=True)
    entidad_tipo = Column(String(80), nullable=False, index=True)
    entidad_id = Column(String(80), nullable=True, index=True)
    origen = Column(String(40), nullable=False, default="admin", server_default="admin")
    request_id = Column(String(100), nullable=True, index=True)
    antes = Column(JSON, nullable=True)
    despues = Column(JSON, nullable=True)
    contexto = Column(JSON, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    actor = relationship("Usuario", foreign_keys=[actor_usuario_id])
