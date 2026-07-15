from sqlalchemy import CheckConstraint, Column, Date, DateTime, Integer, String, Text, func

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
    )

    id = Column(Integer, primary_key=True)
    titulo = Column(String(120), nullable=False)
    tipo = Column(String(20), nullable=False)
    fecha_inicio = Column(Date, nullable=False, index=True)
    fecha_fin = Column(Date, nullable=False, index=True)
    notas = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
