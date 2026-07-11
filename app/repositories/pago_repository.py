"""
Repository de Pagos. Responsabilidad única: acceso a datos.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.pago import Pago


class PagoRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear(self, pago: Pago) -> Pago:
        self.db.add(pago)
        self.db.commit()
        self.db.refresh(pago)
        return pago

    def obtener_por_id(self, pago_id: int) -> Optional[Pago]:
        return self.db.query(Pago).filter(Pago.id == pago_id).first()

    def listar_por_reservacion(self, reservacion_id: int) -> list[Pago]:
        return (
            self.db.query(Pago)
            .filter(Pago.reservacion_id == reservacion_id)
            .order_by(Pago.fecha_pago.asc())
            .all()
        )

    def listar(
        self,
        reservacion_id: Optional[int] = None,
        tipo: Optional[str] = None,
        metodo_pago: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Pago]:
        query = self.db.query(Pago)
        if reservacion_id is not None:
            query = query.filter(Pago.reservacion_id == reservacion_id)
        if tipo is not None:
            query = query.filter(Pago.tipo == tipo)
        if metodo_pago is not None:
            query = query.filter(Pago.metodo_pago == metodo_pago)
        return query.order_by(Pago.id.desc()).offset(offset).limit(limit).all()
