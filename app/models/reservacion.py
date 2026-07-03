from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base

ESTADOS_RESERVACION = ("pendiente", "confirmada", "completada", "cancelada")
ESTADOS_ACTIVOS = ("pendiente", "confirmada")
ORIGENES_RESERVACION = ("recepcion", "recepcion_express", "portal", "telefono")


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
        # Regla de negocio: un cliente solo puede tener una reservación
        # activa (pendiente o confirmada) a la vez. Índice único parcial,
        # aplicado a nivel de base de datos para evitar condiciones de
        # carrera si dos operadores crean una reservación al mismo tiempo.
        Index(
            "ux_reservaciones_una_activa_por_cliente",
            "cliente_id",
            unique=True,
            postgresql_where=text("estado IN ('pendiente', 'confirmada')"),
        ),
    )

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    fecha_reservacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_visita = Column(Date, nullable=False, index=True)
    num_personas = Column(Integer, nullable=False)

    estado = Column(String(20), nullable=False, default="pendiente")
    origen = Column(String(30), nullable=False, default="recepcion")

    total = Column(Numeric(10, 2), nullable=False)
    monto_pagado = Column(Numeric(10, 2), nullable=False, default=0)

    notas = Column(Text, nullable=True)

    fecha_creacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    fecha_actualizacion = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    cliente = relationship("Cliente", back_populates="reservaciones")
    servicio = relationship("Servicio", back_populates="reservaciones")
    pagos = relationship("Pago", back_populates="reservacion")

    @property
    def saldo_pendiente(self):
        """Calculado en Python, no en la BD: total - lo pagado hasta ahora."""
        if self.total is None or self.monto_pagado is None:
            return None
        return self.total - self.monto_pagado

    def __repr__(self):
        return f"<Reservacion id={self.id} cliente_id={self.cliente_id} estado={self.estado!r}>"
