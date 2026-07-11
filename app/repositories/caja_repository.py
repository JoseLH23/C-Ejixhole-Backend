"""
Repository de Caja. Responsabilidad única: acceso a datos. Ninguna
regla de negocio vive aquí (eso es CajaService).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models.caja import CajaMovimiento, CajaSesion


class CajaRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear_sesion(self, sesion: CajaSesion) -> CajaSesion:
        self.db.add(sesion)
        self.db.commit()
        self.db.refresh(sesion)
        return sesion

    def obtener_sesion_por_id(self, sesion_id: int) -> Optional[CajaSesion]:
        return self.db.query(CajaSesion).filter(CajaSesion.id == sesion_id).first()

    def obtener_sesion_abierta_por_usuario(self, usuario_id: int) -> Optional[CajaSesion]:
        return (
            self.db.query(CajaSesion)
            .filter(CajaSesion.usuario_id == usuario_id, CajaSesion.estado == "abierta")
            .first()
        )

    def listar_sesiones(
        self,
        usuario_id: Optional[int] = None,
        estado: Optional[str] = None,
        desde: Optional[datetime] = None,
        hasta: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CajaSesion]:
        query = self.db.query(CajaSesion)
        if usuario_id is not None:
            query = query.filter(CajaSesion.usuario_id == usuario_id)
        if estado is not None:
            query = query.filter(CajaSesion.estado == estado)
        if desde is not None:
            query = query.filter(CajaSesion.fecha_apertura >= desde)
        if hasta is not None:
            query = query.filter(CajaSesion.fecha_apertura < hasta)
        return query.order_by(CajaSesion.id.desc()).offset(offset).limit(limit).all()

    def guardar_sesion(self, sesion: CajaSesion) -> CajaSesion:
        self.db.commit()
        self.db.refresh(sesion)
        return sesion

    def crear_movimiento(self, movimiento: CajaMovimiento) -> CajaMovimiento:
        self.db.add(movimiento)
        self.db.commit()
        self.db.refresh(movimiento)
        return movimiento

    def listar_movimientos(self, sesion_id: int) -> list[CajaMovimiento]:
        return (
            self.db.query(CajaMovimiento)
            .filter(CajaMovimiento.caja_sesion_id == sesion_id)
            .order_by(CajaMovimiento.id.asc())
            .all()
        )
