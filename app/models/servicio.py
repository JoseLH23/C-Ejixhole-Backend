from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.unidad_hospedaje import TIPOS_UNIDAD


_VALORES_TIPO_UNIDAD = "', '".join(TIPOS_UNIDAD)


class Servicio(Base):
    __tablename__ = "servicios"
    __table_args__ = (
        CheckConstraint("precio >= 0", name="ck_servicios_precio_positivo"),
        CheckConstraint(
            f"tipo_unidad_hospedaje IN ('{_VALORES_TIPO_UNIDAD}') OR tipo_unidad_hospedaje IS NULL",
            name="ck_servicios_tipo_unidad_hospedaje_valido",
        ),
    )

    id = Column(Integer, primary_key=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text, nullable=True)
    precio = Column(Numeric(10, 2), nullable=False)
    duracion_minutos = Column(Integer, nullable=True)
    capacidad_maxima = Column(Integer, nullable=True)
    categoria = Column(String(80), nullable=True)
    # ME-11 (auditoría de seguridad 13/jul/2026), reincidencia detectada
    # 15/jul/2026: el servicio "Cabañas" vs "Habitaciones" se resolvía
    # por Servicio.nombre (texto libre editable desde el módulo
    # Servicios) — renombrarlo rompía en silencio la creación de
    # reservaciones de hospedaje. Mismo patrón que tipo_unidad en
    # UnidadHospedaje: campo real y estable, NULL para cualquier
    # servicio que no sea de la categoría "hospedaje". Ver migración
    # 0009_servicio_tipo_hospedaje.
    tipo_unidad_hospedaje = Column(String(20), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    # Distingue lo que SÍ se puede reservar/pagar en el portal (Acceso al
    # parque, Camping, Cabañas, Habitaciones) de lo que solo se muestra
    # como catálogo informativo (lancha, tubing, caballo, snorkel, etc. —
    # se contratan ya estando en el parque, sujeto a disponibilidad).
    reservable = Column(Boolean, nullable=False, default=False)
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    reservaciones = relationship("Reservacion", back_populates="servicio")

    def __repr__(self):
        return f"<Servicio id={self.id} nombre={self.nombre!r}>"
