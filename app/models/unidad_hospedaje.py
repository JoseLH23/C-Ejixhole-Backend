"""
Unidades de hospedaje individuales (Habitación 1, Habitación 2,
Cabaña 1, ...) — a diferencia de Camping (sin límite, no necesita
disponibilidad), cada unidad de hospedaje necesita rastrear su propia
ocupación por noche para no aceptar dos reservaciones que se traslapen.

Ver docs/portal-publico-fase-1.md para el diseño completo acordado.
"""
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class UnidadHospedaje(Base):
    __tablename__ = "unidades_hospedaje"
    __table_args__ = (
        CheckConstraint("capacidad_maxima > 0", name="ck_unidades_hospedaje_capacidad_positiva"),
        CheckConstraint("precio_por_noche >= 0", name="ck_unidades_hospedaje_precio_positivo"),
    )

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False, unique=True)
    capacidad_maxima = Column(Integer, nullable=False)
    precio_por_noche = Column(Numeric(10, 2), nullable=False)
    activa = Column(Boolean, nullable=False, default=True)

    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    reservaciones = relationship("Reservacion", back_populates="unidad_hospedaje")

    def __repr__(self):
        return f"<UnidadHospedaje id={self.id} nombre={self.nombre!r}>"
