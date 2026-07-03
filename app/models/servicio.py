from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class Servicio(Base):
    __tablename__ = "servicios"
    __table_args__ = (CheckConstraint("precio >= 0", name="ck_servicios_precio_positivo"),)

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio = Column(Numeric(10, 2), nullable=False)
    duracion_minutos = Column(Integer, nullable=True)
    capacidad_maxima = Column(Integer, nullable=True)
    categoria = Column(String(80), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    reservaciones = relationship("Reservacion", back_populates="servicio")

    def __repr__(self):
        return f"<Servicio id={self.id} nombre={self.nombre!r}>"
