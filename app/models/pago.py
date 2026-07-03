from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base

TIPOS_PAGO = ("anticipo", "pago_completo", "pago_saldo", "reembolso")
METODOS_PAGO = ("efectivo", "tarjeta", "transferencia", "otro")


class Pago(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_pagos_monto_positivo"),
        CheckConstraint(f"tipo IN {TIPOS_PAGO}", name="ck_pagos_tipo_valido"),
        CheckConstraint(f"metodo_pago IN {METODOS_PAGO}", name="ck_pagos_metodo_valido"),
    )

    id = Column(Integer, primary_key=True)
    reservacion_id = Column(Integer, ForeignKey("reservaciones.id"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    monto = Column(Numeric(10, 2), nullable=False)
    tipo = Column(String(20), nullable=False)
    metodo_pago = Column(String(20), nullable=False)
    referencia = Column(String(100), nullable=True)
    notas = Column(Text, nullable=True)

    fecha_pago = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    reservacion = relationship("Reservacion", back_populates="pagos")
    movimientos_caja = relationship("CajaMovimiento", back_populates="pago")

    def __repr__(self):
        return f"<Pago id={self.id} reservacion_id={self.reservacion_id} monto={self.monto}>"
