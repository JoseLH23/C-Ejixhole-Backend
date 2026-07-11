"""
Repository de Servicios. Responsabilidad única: acceso a datos.
Ninguna regla de negocio vive aquí (eso es ServicioService).
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.servicio import Servicio


class ServicioRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear(self, servicio: Servicio) -> Servicio:
        self.db.add(servicio)
        self.db.commit()
        self.db.refresh(servicio)
        return servicio

    def obtener_por_id(self, servicio_id: int) -> Optional[Servicio]:
        return self.db.query(Servicio).filter(Servicio.id == servicio_id).first()

    def listar(
        self,
        solo_activos: bool = True,
        categoria: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Servicio]:
        query = self.db.query(Servicio)
        if solo_activos:
            query = query.filter(Servicio.activo.is_(True))
        if categoria is not None:
            query = query.filter(Servicio.categoria == categoria)
        return query.order_by(Servicio.id.desc()).offset(offset).limit(limit).all()

    def actualizar(self, servicio: Servicio, datos: dict) -> Servicio:
        for campo, valor in datos.items():
            setattr(servicio, campo, valor)
        self.db.commit()
        self.db.refresh(servicio)
        return servicio

    def desactivar(self, servicio: Servicio) -> Servicio:
        servicio.activo = False
        self.db.commit()
        self.db.refresh(servicio)
        return servicio
