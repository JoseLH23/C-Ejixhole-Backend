from sqlalchemy import (
    CheckConstraint,
    Column,
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

ESTADOS_CAJA = ("abierta", "cerrada")
TIPOS_MOVIMIENTO = ("ingreso", "egreso")


class CajaSesion(Base):
    __tablename__ = "caja_sesiones"
    __table_args__ = (
        CheckConstraint(f"estado IN {ESTADOS_CAJA}", name="ck_caja_sesiones_estado_valido"),
        # Regla de negocio: un usuario no puede tener dos sesiones de
        # caja abiertas al mismo tiempo. sqlite_where se agrega junto a
        # postgresql_where para que las pruebas con SQLite en memoria
        # repliquen el mismo comportamiento parcial (mismo ajuste que
        # se hizo en reservaciones — sin esto, SQLite bloquearía que un
        # usuario abra una nueva caja después de haber cerrado la
        # anterior).
        Index(
            "ux_caja_sesion_abierta_por_usuario",
            "usuario_id",
            unique=True,
            postgresql_where=text("estado = 'abierta'"),
            sqlite_where=text("estado = 'abierta'"),
        ),
    )

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    fecha_apertura = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    monto_apertura = Column(Numeric(10, 2), nullable=False, default=0)

    fecha_cierre = Column(DateTime(timezone=True), nullable=True)
    monto_cierre_esperado = Column(Numeric(10, 2), nullable=True)
    monto_cierre_real = Column(Numeric(10, 2), nullable=True)
    diferencia = Column(Numeric(10, 2), nullable=True)

    estado = Column(String(20), nullable=False, default="abierta")
    notas = Column(Text, nullable=True)

    movimientos = relationship("CajaMovimiento", back_populates="sesion")

    @property
    def saldo_actual(self):
        """
        Calculado en Python, no en la BD (mismo patrón que
        Reservacion.saldo_pendiente): monto_apertura + ingresos - egresos
        de todos los movimientos registrados hasta ahora.
        """
        from decimal import Decimal

        ingresos = sum((m.monto for m in self.movimientos if m.tipo == "ingreso"), Decimal("0"))
        egresos = sum((m.monto for m in self.movimientos if m.tipo == "egreso"), Decimal("0"))
        return self.monto_apertura + ingresos - egresos

    def __repr__(self):
        return f"<CajaSesion id={self.id} usuario_id={self.usuario_id} estado={self.estado!r}>"


class CajaMovimiento(Base):
    __tablename__ = "caja_movimientos"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_caja_movimientos_monto_positivo"),
        CheckConstraint(f"tipo IN {TIPOS_MOVIMIENTO}", name="ck_caja_movimientos_tipo_valido"),
    )

    id = Column(Integer, primary_key=True)
    caja_sesion_id = Column(Integer, ForeignKey("caja_sesiones.id"), nullable=False, index=True)
    pago_id = Column(Integer, ForeignKey("pagos.id"), nullable=True)  # NULL = movimiento manual
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    tipo = Column(String(20), nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    concepto = Column(String(255), nullable=False)

    fecha = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    sesion = relationship("CajaSesion", back_populates="movimientos")
    pago = relationship("Pago", back_populates="movimientos_caja")

    def __repr__(self):
        return f"<CajaMovimiento id={self.id} tipo={self.tipo!r} monto={self.monto}>"
