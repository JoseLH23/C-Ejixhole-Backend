"""
Repository de Reservaciones. Responsabilidad única: acceso a datos.
Ninguna regla de negocio vive aquí (eso es ReservacionService).
"""
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models.reservacion import ESTADOS_ACTIVOS, Reservacion


class ReservacionRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear(self, reservacion: Reservacion) -> Reservacion:
        self.db.add(reservacion)
        self.db.commit()
        self.db.refresh(reservacion)
        return reservacion

    def obtener_por_id(self, reservacion_id: int) -> Optional[Reservacion]:
        return self.db.query(Reservacion).filter(Reservacion.id == reservacion_id).first()

    def obtener_activa_por_cliente(self, cliente_id: int) -> Optional[Reservacion]:
        return (
            self.db.query(Reservacion)
            .filter(Reservacion.cliente_id == cliente_id, Reservacion.estado.in_(ESTADOS_ACTIVOS))
            .first()
        )

    def listar(
        self,
        cliente_id: Optional[int] = None,
        servicio_id: Optional[int] = None,
        estado: Optional[str] = None,
        fecha_desde: Optional[date] = None,
        fecha_hasta: Optional[date] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Reservacion]:
        query = self.db.query(Reservacion)

        if cliente_id is not None:
            query = query.filter(Reservacion.cliente_id == cliente_id)
        if servicio_id is not None:
            query = query.filter(Reservacion.servicio_id == servicio_id)
        if estado is not None:
            query = query.filter(Reservacion.estado == estado)
        if fecha_desde is not None:
            query = query.filter(Reservacion.fecha_visita >= fecha_desde)
        if fecha_hasta is not None:
            query = query.filter(Reservacion.fecha_visita <= fecha_hasta)

        return query.order_by(Reservacion.id.desc()).offset(offset).limit(limit).all()

    def actualizar_estado(self, reservacion: Reservacion, nuevo_estado: str) -> Reservacion:
        reservacion.estado = nuevo_estado
        self.db.commit()
        self.db.refresh(reservacion)
        return reservacion
