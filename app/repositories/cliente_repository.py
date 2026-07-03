"""
Repository de Clientes.

Responsabilidad única: acceso a datos. Ninguna regla de negocio vive
aquí (eso es responsabilidad de ClienteService). Si mañana cambiamos
de ORM o agregamos caché, solo se toca este archivo.
"""
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.cliente import Cliente


class ClienteRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear(self, cliente: Cliente) -> Cliente:
        self.db.add(cliente)
        self.db.commit()
        self.db.refresh(cliente)
        return cliente

    def obtener_por_id(self, cliente_id: int) -> Optional[Cliente]:
        return self.db.query(Cliente).filter(Cliente.id == cliente_id).first()

    def listar(self, solo_activos: bool = True, limit: int = 100, offset: int = 0) -> list[Cliente]:
        query = self.db.query(Cliente)
        if solo_activos:
            query = query.filter(Cliente.activo.is_(True))
        return query.order_by(Cliente.id.desc()).offset(offset).limit(limit).all()

    def buscar_por_telefono_o_email(
        self, telefono: Optional[str], email: Optional[str]
    ) -> list[Cliente]:
        condiciones = []
        if telefono:
            condiciones.append(Cliente.telefono == telefono)
        if email:
            condiciones.append(Cliente.email == email)

        if not condiciones:
            return []

        return self.db.query(Cliente).filter(or_(*condiciones)).all()

    def actualizar(self, cliente: Cliente, datos: dict) -> Cliente:
        for campo, valor in datos.items():
            setattr(cliente, campo, valor)
        self.db.commit()
        self.db.refresh(cliente)
        return cliente

    def desactivar(self, cliente: Cliente) -> Cliente:
        cliente.activo = False
        self.db.commit()
        self.db.refresh(cliente)
        return cliente
