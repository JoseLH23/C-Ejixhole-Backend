"""
Repository de Reportes. Responsabilidad única: traer los registros
crudos filtrados. TODA la agregación por periodo (día/semana/mes) se
hace en ReporteService, en Python — ver docs/modulos/reportes-diseno.md
sección 1 para el porqué.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.pago import Pago
from app.models.reservacion import ESTADOS_ACTIVOS, Reservacion
from app.models.servicio import Servicio


class ReporteRepository:
    def __init__(self, db: Session):
        self.db = db

    def obtener_pagos(
        self, metodo_pago: Optional[str] = None, servicio_id: Optional[int] = None
    ) -> list[Pago]:
        """
        No filtra por fecha aquí (eso lo hace el Service en Python).
        Sí filtra por metodo_pago/servicio_id en SQL porque no involucra
        fechas ni tipos de dato con comportamiento distinto entre
        motores.
        """
        query = self.db.query(Pago)
        if metodo_pago is not None:
            query = query.filter(Pago.metodo_pago == metodo_pago)
        if servicio_id is not None:
            query = query.join(Reservacion, Pago.reservacion_id == Reservacion.id).filter(
                Reservacion.servicio_id == servicio_id
            )
        return query.order_by(Pago.fecha_pago.asc()).all()

    def obtener_reservaciones_activas(self) -> list[Reservacion]:
        """Reservaciones pendientes o confirmadas — candidatas a tener saldo pendiente."""
        return self.db.query(Reservacion).filter(Reservacion.estado.in_(ESTADOS_ACTIVOS)).all()

    def obtener_reservaciones(
        self, servicio_id: Optional[int] = None, origen: Optional[str] = None
    ) -> list[Reservacion]:
        """
        Trae reservaciones sin filtrar por fecha ni estado (eso lo hace
        el Service en Python, sobre fecha_visita o fecha_creacion según
        el reporte). Solo filtra en SQL las dimensiones sin ambigüedad
        de fecha/motor: servicio_id, origen.
        """
        query = self.db.query(Reservacion)
        if servicio_id is not None:
            query = query.filter(Reservacion.servicio_id == servicio_id)
        if origen is not None:
            query = query.filter(Reservacion.origen == origen)
        return query.all()

    def obtener_servicios(
        self, servicio_id: Optional[int] = None, solo_activos: bool = True
    ) -> list[Servicio]:
        query = self.db.query(Servicio)
        if solo_activos:
            query = query.filter(Servicio.activo.is_(True))
        if servicio_id is not None:
            query = query.filter(Servicio.id == servicio_id)
        return query.all()

    def obtener_clientes(self) -> list[Cliente]:
        """Sin filtro de fecha (eso lo hace el Service en Python, sobre fecha_creacion)."""
        return self.db.query(Cliente).all()
