"""
AL-04 (auditoría de seguridad 13/jul/2026): protección real contra
doble clic / doble envío en operaciones críticas (crear reservación,
registrar pago, movimientos de caja).

Cada fila representa UN intento de una operación identificada por
`clave` (la Idempotency-Key que manda el cliente) + `endpoint`. Mientras
`response_body` es NULL, la operación real todavía está en curso — eso
es lo que cierra la condición de carrera de dos clics simultáneos, no
solo dos clics secuenciales.
"""
from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint, func

from app.database import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("clave", "endpoint", name="uq_idempotency_clave_endpoint"),
    )

    id = Column(Integer, primary_key=True)
    clave = Column(String(128), nullable=False, index=True)
    endpoint = Column(String(100), nullable=False)
    request_hash = Column(String(64), nullable=False)
    # NULL = la operación real todavía está en curso (se reservó la
    # clave pero no ha terminado). Con contenido = ya terminó, y este
    # es el JSON exacto que se le devuelve a cualquier reintento con
    # la misma clave.
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
