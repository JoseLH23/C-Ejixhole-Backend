from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base

TIPOS_EVENTO_CALENDARIO = ("bloqueo", "mantenimiento", "recordatorio", "campana")


class EventoCalendario(Base):
    __tablename__ = "eventos_calendario"
    __table_args__ = (
        CheckConstraint(
            f"tipo IN {TIPOS_EVENTO_CALENDARIO}",
            name="ck_eventos_calendario_tipo_valido",
        ),
        CheckConstraint(
            "fecha_fin >= fecha_inicio",
            name="ck_eventos_calendario_rango_valido",
        ),
        CheckConstraint(
            "unidad_hospedaje_id IS NULL OR tipo = 'bloqueo'",
            name="ck_eventos_calendario_unidad_solo_bloqueo",
        ),
    )

    id = Column(Integer, primary_key=True)
    titulo = Column(String(120), nullable=False)
    tipo = Column(String(20), nullable=False)
    fecha_inicio = Column(Date, nullable=False, index=True)
    fecha_fin = Column(Date, nullable=False, index=True)
    notas = Column(Text, nullable=True)
    # NULL = bloqueo global del parque. Con valor = solo esa unidad.
    unidad_hospedaje_id = Column(
        Integer,
        ForeignKey("unidades_hospedaje.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    unidad_hospedaje = relationship("UnidadHospedaje")
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
