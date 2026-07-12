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

    def existe_traslape_unidad_hospedaje(
        self,
        unidad_hospedaje_id: int,
        fecha_llegada: date,
        fecha_salida: date,
        excluir_reservacion_id: Optional[int] = None,
    ) -> bool:
        """
        True si la unidad ya tiene una reservación activa (pendiente o
        confirmada) que se traslapa con el rango [fecha_llegada, fecha_salida).
        Camping y entrada nunca llaman esto — no tienen unidad ni límite.

        Traslape estándar de rangos de fechas: dos rangos [A,B) y [C,D)
        se traslapan si A < D y C < B. Se usa "salida exclusiva" (el
        día de salida de una reservación SÍ puede ser el día de llegada
        de la siguiente — el cliente se va en la mañana, el nuevo llega
        en la tarde).

        `excluir_reservacion_id`: al EDITAR una reservación existente,
        se debe ignorar su propio registro en este chequeo — si no, una
        reservación de hospedaje siempre "chocaría consigo misma" y
        sería imposible editarle las fechas sin cancelarla primero.
        `crear()`/`cotizar()` nunca lo pasan (no aplica, todavía no existe).
        """
        query = self.db.query(Reservacion).filter(
            Reservacion.unidad_hospedaje_id == unidad_hospedaje_id,
            Reservacion.estado.in_(ESTADOS_ACTIVOS),
            Reservacion.fecha_llegada < fecha_salida,
            Reservacion.fecha_salida > fecha_llegada,
        )
        if excluir_reservacion_id is not None:
            query = query.filter(Reservacion.id != excluir_reservacion_id)
        return query.first() is not None

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

    def actualizar(self, reservacion: Reservacion, cambios: dict) -> Reservacion:
        """Aplica cambios ya validados por ReservacionService.actualizar() —
        este método no valida nada, solo persiste."""
        for campo, valor in cambios.items():
            setattr(reservacion, campo, valor)
        self.db.commit()
        self.db.refresh(reservacion)
        return reservacion
