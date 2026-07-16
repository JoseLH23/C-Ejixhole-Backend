"""Reglas del flujo operativo de llegada y salida del visitante."""
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.reservacion import Reservacion


class FlujoVisitaService:
    def __init__(self, db: Session):
        self.db = db

    def _obtener_bloqueada(self, reservacion_id: int) -> Reservacion:
        reservacion = (
            self.db.query(Reservacion)
            .filter(Reservacion.id == reservacion_id)
            .with_for_update()
            .first()
        )
        if not reservacion:
            raise HTTPException(status_code=404, detail="Reservación no encontrada.")
        return reservacion

    def check_in(self, reservacion_id: int, usuario_id: int) -> Reservacion:
        reservacion = self._obtener_bloqueada(reservacion_id)
        if reservacion.estado != "confirmada":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "El check-in solo puede hacerse sobre una reservación confirmada. "
                    f"Estado actual: {reservacion.estado}."
                ),
            )

        reservacion.estado = "en_curso"
        reservacion.fecha_checkin = datetime.now(timezone.utc)
        reservacion.checkin_usuario_id = usuario_id
        self.db.commit()
        self.db.refresh(reservacion)
        return reservacion

    def check_out(self, reservacion_id: int, usuario_id: int) -> Reservacion:
        reservacion = self._obtener_bloqueada(reservacion_id)
        if reservacion.estado != "en_curso":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "El check-out solo puede hacerse después del check-in. "
                    f"Estado actual: {reservacion.estado}."
                ),
            )
        if not reservacion.pago_completo:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "No se puede completar la visita mientras exista saldo pendiente. "
                    f"Saldo actual: ${reservacion.saldo_pendiente}."
                ),
            )

        reservacion.estado = "completada"
        reservacion.fecha_checkout = datetime.now(timezone.utc)
        reservacion.checkout_usuario_id = usuario_id
        self.db.commit()
        self.db.refresh(reservacion)
        return reservacion
