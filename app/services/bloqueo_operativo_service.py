from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.evento_calendario import EventoCalendario


class BloqueoOperativoService:
    """Valida cierres operativos compartidos por rutas internas y públicas."""

    def __init__(self, db: Session):
        self.db = db

    def buscar_traslape(
        self,
        fecha_llegada: date,
        fecha_salida: date,
        tipo_reservacion: str,
    ) -> EventoCalendario | None:
        query = self.db.query(EventoCalendario).filter(EventoCalendario.tipo == "bloqueo")

        if tipo_reservacion == "entrada":
            query = query.filter(
                EventoCalendario.fecha_inicio <= fecha_llegada,
                EventoCalendario.fecha_fin >= fecha_llegada,
            )
        else:
            # Camping y hospedaje ocupan noches en [llegada, salida).
            # Un bloqueo que empieza el día de salida no impide el check-out.
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
    ) -> None:
        bloqueo = self.buscar_traslape(fecha_llegada, fecha_salida, tipo_reservacion)
        if bloqueo is None:
            return

        rango = (
            bloqueo.fecha_inicio.isoformat()
            if bloqueo.fecha_inicio == bloqueo.fecha_fin
            else f"{bloqueo.fecha_inicio.isoformat()} al {bloqueo.fecha_fin.isoformat()}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pueden crear reservaciones en esas fechas por el bloqueo operativo: {bloqueo.titulo} ({rango}).",
        )

    def hay_disponibilidad(
        self,
        fecha_llegada: date,
        fecha_salida: date,
        tipo_reservacion: str,
    ) -> bool:
        return self.buscar_traslape(fecha_llegada, fecha_salida, tipo_reservacion) is None
