from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

ESTADOS_RESERVACION = ("pendiente", "confirmada", "en_curso", "completada", "cancelada")
ESTADOS_ACTIVOS = ("pendiente", "confirmada", "en_curso")
ORIGENES_RESERVACION = ("recepcion", "recepcion_express", "portal", "telefono")
TIPOS_RESERVACION = ("entrada", "camping", "hospedaje")


class Reservacion(Base):
    __tablename__ = "reservaciones"
    __table_args__ = (
        CheckConstraint("num_personas > 0", name="ck_reservaciones_num_personas_positivo"),
        CheckConstraint("total >= 0", name="ck_reservaciones_total_positivo"),
        CheckConstraint("monto_pagado >= 0", name="ck_reservaciones_monto_pagado_positivo"),
        CheckConstraint(
            f"estado IN {ESTADOS_RESERVACION}", name="ck_reservaciones_estado_valido"
        ),
        CheckConstraint(
            f"origen IN {ORIGENES_RESERVACION}", name="ck_reservaciones_origen_valido"
        ),
        CheckConstraint(
            f"tipo_reservacion IN {TIPOS_RESERVACION}", name="ck_reservaciones_tipo_valido"
        ),
    )

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    unidad_hospedaje_id = Column(
        Integer, ForeignKey("unidades_hospedaje.id"), nullable=True, index=True
    )

    fecha_reservacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_visita = Column(Date, nullable=False, index=True)
    fecha_llegada = Column(Date, nullable=True, index=True)
    fecha_salida = Column(Date, nullable=True)
    num_personas = Column(Integer, nullable=False)

    estado = Column(String(20), nullable=False, default="pendiente")
    origen = Column(String(30), nullable=False, default="recepcion")
    tipo_reservacion = Column(String(20), nullable=False, default="entrada")

    total = Column(Numeric(10, 2), nullable=False)
    monto_pagado = Column(Numeric(10, 2), nullable=False, default=0)

    # Trazabilidad del flujo operativo. `en_curso` significa que el visitante
    # ya hizo check-in. El check-out cierra la visita y deja el estado como
    # `completada`. Los usuarios se conservan para auditoría operativa.
    fecha_checkin = Column(DateTime(timezone=True), nullable=True)
    checkin_usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    fecha_checkout = Column(DateTime(timezone=True), nullable=True)
    checkout_usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )

    notas = Column(Text, nullable=True)

    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    cliente = relationship("Cliente", back_populates="reservaciones")
    servicio = relationship("Servicio", back_populates="reservaciones")
    unidad_hospedaje = relationship("UnidadHospedaje", back_populates="reservaciones")
    pagos = relationship("Pago", back_populates="reservacion")

    @property
    def saldo_pendiente(self):
        """Calculado en Python, no en la BD: total - lo pagado hasta ahora."""
        if self.total is None or self.monto_pagado is None:
            return None
        return self.total - self.monto_pagado

    @property
    def pago_completo(self) -> bool:
        return self.saldo_pendiente is not None and self.saldo_pendiente <= 0

    def __repr__(self):
        return f"<Reservacion id={self.id} cliente_id={self.cliente_id} estado={self.estado!r}>"
