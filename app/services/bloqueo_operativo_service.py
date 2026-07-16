from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.evento_calendario import EventoCalendario


class BloqueoOperativoService:
    """Valida cierres globales y cierres exclusivos de una unidad."""

    def __init__(self, db: Session):
        self.db = db

    def listar_bloqueos(self, desde: date, hasta: date) -> list[EventoCalendario]:
        """Devuelve cierres globales; los cierres por unidad se consultan
        mediante disponibilidad para no presentarlos como cierre del parque."""
        return (
            self.db.query(EventoCalendario)
            .filter(
                EventoCalendario.tipo == "bloqueo",
                EventoCalendario.unidad_hospedaje_id.is_(None),
                EventoCalendario.fecha_inicio <= hasta,
                EventoCalendario.fecha_fin >= desde,
            )
            .order_by(EventoCalendario.fecha_inicio.asc(), EventoCalendario.id.asc())
            .all()
        )

    def buscar_traslape(
        self,
        fecha_llegada: date,
        fecha_salida: date,
        tipo_reservacion: str,
        unidad_hospedaje_id: int | None = None,
    ) -> EventoCalendario | None:
        query = self.db.query(EventoCalendario).filter(EventoCalendario.tipo == "bloqueo")

        if tipo_reservacion == "hospedaje" and unidad_hospedaje_id is not None:
            query = query.filter(
                or_(
                    EventoCalendario.unidad_hospedaje_id.is_(None),
                    EventoCalendario.unidad_hospedaje_id == unidad_hospedaje_id,
                )
            )
        else:
            query = query.filter(EventoCalendario.unidad_hospedaje_id.is_(None))

        if tipo_reservacion == "entrada":
            query = query.filter(
                EventoCalendario.fecha_inicio <= fecha_llegada,
                EventoCalendario.fecha_fin >= fecha_llegada,
            )
        else:
            query = query.filter(
                EventoCalendario.fecha_inicio < fecha_salida,
                EventoCalendario.fecha_fin >= fecha_llegada,
            )

        return query.order_by(EventoCalendario.fecha_inicio.asc()).first()

    def validar_disponibilidad(
        self,
        fecha_llegada: date,
        fecha_salida: date,
        tipo_reservacion: str,
        unidad_hospedaje_id: int | None = None,
    ) -> None:
        bloqueo = self.buscar_traslape(
            fecha_llegada,
            fecha_salida,
            tipo_reservacion,
            unidad_hospedaje_id,
        )
        if bloqueo is None:
            return

        rango = (
            bloqueo.fecha_inicio.isoformat()
            if bloqueo.fecha_inicio == bloqueo.fecha_fin
            else f"{bloqueo.fecha_inicio.isoformat()} al {bloqueo.fecha_fin.isoformat()}"
        )
        alcance = "esa unidad" if bloqueo.unidad_hospedaje_id is not None else "el parque"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden crear reservaciones para {alcance} por el bloqueo operativo: {bloqueo.titulo} ({rango}).",
        )

    def hay_disponibilidad(
        self,
        fecha_llegada: date,
        fecha_salida: date,
        tipo_reservacion: str,
        unidad_hospedaje_id: int | None = None,
    ) -> bool:
        return (
            self.buscar_traslape(
                fecha_llegada,
                fecha_salida,
                tipo_reservacion,
                unidad_hospedaje_id,
            )
            is None
        )
