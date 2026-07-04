"""
Service de Reservaciones. Reglas de negocio; el acceso a datos se
delega a ReservacionRepository (y a los repos/queries de Cliente y
Servicio para validar que existen).
"""
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.reservacion import ESTADOS_RESERVACION, Reservacion
from app.models.servicio import Servicio
from app.repositories.reservacion_repository import ReservacionRepository

ESTADOS_TERMINALES = ("completada", "cancelada")


class ReservacionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = ReservacionRepository(db)

    def crear(
        self,
        cliente_id: int,
        servicio_id: int,
        usuario_id: int,
        fecha_visita: date,
        num_personas: int,
        origen: str,
        notas: str | None,
    ) -> Reservacion:
        cliente = self.db.query(Cliente).filter(Cliente.id == cliente_id).first()
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente no encontrado.")
        if not cliente.activo:
            raise HTTPException(
                status_code=400, detail="No se puede reservar para un cliente desactivado."
            )

        servicio = self.db.query(Servicio).filter(Servicio.id == servicio_id).first()
        if not servicio:
            raise HTTPException(status_code=404, detail="Servicio no encontrado.")
        if not servicio.activo:
            raise HTTPException(status_code=400, detail="Este servicio ya no está disponible.")

        if servicio.capacidad_maxima and num_personas > servicio.capacidad_maxima:
            raise HTTPException(
                status_code=400,
                detail=f"Este servicio admite máximo {servicio.capacidad_maxima} personas.",
            )

        # Chequeo previo "amigable": el índice único parcial en Postgres
        # es la garantía real contra condiciones de carrera; este
        # chequeo solo existe para devolver un mensaje claro en el caso
        # normal (sin carrera).
        activa = self.repo.obtener_activa_por_cliente(cliente_id)
        if activa:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Este cliente ya tiene una reservación activa (id={activa.id}, "
                    f"estado={activa.estado}). Debe completarse o cancelarse antes de "
                    "crear una nueva."
                ),
            )

        total = servicio.precio * num_personas

        reservacion = Reservacion(
            cliente_id=cliente_id,
            servicio_id=servicio_id,
            usuario_id=usuario_id,
            fecha_visita=fecha_visita,
            num_personas=num_personas,
            origen=origen,
            total=total,
            monto_pagado=0,
            notas=notas,
        )

        try:
            return self.repo.crear(reservacion)
        except IntegrityError:
            # Red de seguridad ante condiciones de carrera reales.
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este cliente ya tiene una reservación activa (detectado al guardar).",
            )

    def obtener_por_id(self, reservacion_id: int) -> Reservacion:
        reservacion = self.repo.obtener_por_id(reservacion_id)
        if not reservacion:
            raise HTTPException(status_code=404, detail="Reservación no encontrada.")
        return reservacion

    def listar(self, **filtros) -> list[Reservacion]:
        return self.repo.listar(**filtros)

    def cambiar_estado(self, reservacion_id: int, nuevo_estado: str) -> Reservacion:
        if nuevo_estado not in ESTADOS_RESERVACION:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {nuevo_estado}")

        reservacion = self.obtener_por_id(reservacion_id)

        if reservacion.estado in ESTADOS_TERMINALES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Esta reservación ya está en estado terminal "
                    f"'{reservacion.estado}' y no puede cambiar de estado."
                ),
            )

        if reservacion.estado == nuevo_estado:
            raise HTTPException(
                status_code=400, detail=f"La reservación ya está en estado '{nuevo_estado}'."
            )

        return self.repo.actualizar_estado(reservacion, nuevo_estado)
