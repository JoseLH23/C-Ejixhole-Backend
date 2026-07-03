from sqlalchemy import BigInteger, CheckConstraint, Column, DateTime, Integer, String, Text, func

from app.database import Base

TIPOS_RESPALDO = ("manual", "automatico")
ESTADOS_RESPALDO = ("exitoso", "fallido")


class Configuracion(Base):
    __tablename__ = "configuracion"

    id = Column(Integer, primary_key=True)
    clave = Column(String(100), nullable=False, unique=True)
    valor = Column(Text, nullable=True)
    descripcion = Column(String(255), nullable=True)
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<Configuracion clave={self.clave!r}>"


class Respaldo(Base):
    __tablename__ = "respaldos"
    __table_args__ = (
        CheckConstraint(f"tipo IN {TIPOS_RESPALDO}", name="ck_respaldos_tipo_valido"),
        CheckConstraint(f"estado IN {ESTADOS_RESPALDO}", name="ck_respaldos_estado_valido"),
    )

    id = Column(Integer, primary_key=True)
    nombre_archivo = Column(String(255), nullable=False)
    ruta = Column(String(500), nullable=False)
    tamano_bytes = Column(BigInteger, nullable=True)
    tipo = Column(String(20), nullable=False, default="manual")
    estado = Column(String(20), nullable=False, default="exitoso")
    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    def __repr__(self):
        return f"<Respaldo id={self.id} archivo={self.nombre_archivo!r}>"
