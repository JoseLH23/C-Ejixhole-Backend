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

ESTADOS_RESERVACION = ("pendiente", "confirmada", "completada", "cancelada")
ESTADOS_ACTIVOS = ("pendiente", "confirmada")
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
        # NOTA (decisión explícita del negocio, ver docs/portal-publico-fase-1.md):
        # antes existía aquí un índice único que impedía que un mismo
        # cliente tuviera más de una reservación activa a la vez. Se
        # eliminó a propósito: con el portal público, un cliente debe
        # poder tener varias reservaciones activas simultáneas (ej. una
        # visita de un día la próxima semana Y un camping dos meses
        # después). Por eso el sistema exige contacto real del cliente
        # (teléfono/email) — para poder resolver cualquier choque
        # manualmente en vez de bloquearlo por regla.
    )

    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False, index=True)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), nullable=False, index=True)
    # Nullable: las reservaciones internas siempre lo llenan (empleado
    # que la capturó). Las del portal público lo dejan vacío — nadie
    # del personal la creó, la hizo el visitante directamente.
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    # Nullable: solo se llena cuando tipo_reservacion == "hospedaje".
    # Camping y entrada no tienen unidad individual (sin límite de cupo).
    unidad_hospedaje_id = Column(
        Integer, ForeignKey("unidades_hospedaje.id"), nullable=True, index=True
    )

    fecha_reservacion = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # fecha_visita se mantiene obligatoria y NUNCA se elimina — todos los
    # Reportes y el Dashboard ya la usan. Para reservaciones nuevas, el
    # servicio la llena automáticamente igual a fecha_llegada, así que
    # nada de lo existente necesita cambiar. fecha_llegada/fecha_salida
    # son las que habilitan el cálculo por noches (camping/hospedaje).
    fecha_visita = Column(Date, nullable=False, index=True)
    fecha_llegada = Column(Date, nullable=True, index=True)
    fecha_salida = Column(Date, nullable=True)
    num_personas = Column(Integer, nullable=False)

    estado = Column(String(20), nullable=False, default="pendiente")
    origen = Column(String(30), nullable=False, default="recepcion")
    # Default "entrada" por compatibilidad con filas ya existentes
    # (todas las reservaciones de antes de esta entrega son, en la
    # práctica, visitas de un día — nunca hospedaje ni camping).
    tipo_reservacion = Column(String(20), nullable=False, default="entrada")

    total = Column(Numeric(10, 2), nullable=False)
    monto_pagado = Column(Numeric(10, 2), nullable=False, default=0)

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

    def __repr__(self):
        return f"<Reservacion id={self.id} cliente_id={self.cliente_id} estado={self.estado!r}>"
