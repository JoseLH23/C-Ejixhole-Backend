from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.evento_calendario import EventoCalendarioCreate, EventoCalendarioOut
from app.services.evento_calendario_service import EventoCalendarioService

router = APIRouter(
    prefix="/eventos-calendario",
    tags=["Calendario"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.post("", response_model=EventoCalendarioOut, status_code=201)
def crear_evento(data: EventoCalendarioCreate, db: Session = Depends(get_db)):
    return EventoCalendarioService(db).crear(**data.model_dump())


@router.get("", response_model=list[EventoCalendarioOut])
def listar_eventos(
    desde: date = Query(...),
    hasta: date = Query(...),
    db: Session = Depends(get_db),
):
    return EventoCalendarioService(db).listar(desde, hasta)


@router.delete("/{evento_id}", status_code=204)
def eliminar_evento(evento_id: int, db: Session = Depends(get_db)):
    EventoCalendarioService(db).eliminar(evento_id)
    return Response(status_code=204)
