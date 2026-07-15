from datetime import date

from sqlalchemy.orm import Session

from app.models.evento_calendario import EventoCalendario


class EventoCalendarioRepository:
    def __init__(self, db: Session):
        self.db = db

    def crear(self, evento: EventoCalendario) -> EventoCalendario:
        self.db.add(evento)
        self.db.commit()
        self.db.refresh(evento)
        return evento

    def listar(self, desde: date, hasta: date) -> list[EventoCalendario]:
        return (
            self.db.query(EventoCalendario)
            .filter(
                EventoCalendario.fecha_inicio <= hasta,
                EventoCalendario.fecha_fin >= desde,
            )
            .order_by(EventoCalendario.fecha_inicio.asc(), EventoCalendario.id.asc())
            .all()
        )

    def obtener_por_id(self, evento_id: int) -> EventoCalendario | None:
        return self.db.query(EventoCalendario).filter(EventoCalendario.id == evento_id).first()

    def eliminar(self, evento: EventoCalendario) -> None:
        self.db.delete(evento)
        self.db.commit()
