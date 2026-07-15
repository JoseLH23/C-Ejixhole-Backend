from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.evento_calendario import EventoCalendario
from app.models.unidad_hospedaje import UnidadHospedaje
from app.repositories.evento_calendario_repository import EventoCalendarioRepository


class EventoCalendarioService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = EventoCalendarioRepository(db)

    def crear(
        self,
        *,
        titulo: str,
        tipo: str,
        fecha_inicio: date,
        fecha_fin: date,
        notas: str | None,
        unidad_hospedaje_id: int | None = None,
    ):
        titulo_limpio = titulo.strip()
        if not titulo_limpio:
            raise HTTPException(status_code=422, detail="El título es obligatorio")
        if fecha_fin < fecha_inicio:
            raise HTTPException(status_code=422, detail="fecha_fin no puede ser anterior a fecha_inicio")
        if unidad_hospedaje_id is not None:
            if tipo != "bloqueo":
                raise HTTPException(status_code=422, detail="La unidad solo puede asignarse a bloqueos")
            unidad = (
                self.db.query(UnidadHospedaje)
                .filter(UnidadHospedaje.id == unidad_hospedaje_id)
                .first()
            )
            if not unidad:
                raise HTTPException(status_code=404, detail="Unidad de hospedaje no encontrada")

        return self.repo.crear(
            EventoCalendario(
                titulo=titulo_limpio,
                tipo=tipo,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                notas=notas.strip() if notas and notas.strip() else None,
                unidad_hospedaje_id=unidad_hospedaje_id,
            )
        )

    def listar(self, desde: date, hasta: date):
        if hasta < desde:
            raise HTTPException(status_code=422, detail="hasta no puede ser anterior a desde")
        return self.repo.listar(desde, hasta)

    def eliminar(self, evento_id: int):
        evento = self.repo.obtener_por_id(evento_id)
        if not evento:
            raise HTTPException(status_code=404, detail="Evento de calendario no encontrado")
        self.repo.eliminar(evento)
