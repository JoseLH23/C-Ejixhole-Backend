from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class TarifaEspecial(Base):
    __tablename__ = "tarifas_especiales"
    __table_args__ = (
        CheckConstraint("fecha_fin >= fecha_inicio", name="ck_tarifas_especiales_rango_valido"),
        CheckConstraint("porcentaje_ajuste >= -100 AND porcentaje_ajuste <= 500", name="ck_tarifas_especiales_porcentaje_valido"),
        CheckConstraint("aplica_a IN ('todos','entrada','camping','hospedaje')", name="ck_tarifas_especiales_aplica_a_valido"),
    )

    id = Column(Integer, primary_key=True)
    nombre = Column(String(120), nullable=False)
    descripcion = Column(Text, nullable=True)
    fecha_inicio = Column(Date, nullable=False, index=True)
    fecha_fin = Column(Date, nullable=False, index=True)
    porcentaje_ajuste = Column(Numeric(7, 2), nullable=False)
    aplica_a = Column(String(20), nullable=False, default="todos")
    dias_semana = Column(JSON, nullable=True)
    prioridad = Column(Integer, nullable=False, default=0)
    unidad_hospedaje_id = Column(Integer, ForeignKey("unidades_hospedaje.id", ondelete="CASCADE"), nullable=True)
    activa = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    unidad_hospedaje = relationship("UnidadHospedaje")
