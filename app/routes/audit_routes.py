from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.audit_event import AuditEventOut
from app.services.audit_service import AuditService

router = APIRouter(
    prefix="/auditoria",
    tags=["Auditoría"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("", response_model=list[AuditEventOut])
def listar_eventos_auditoria(
    entidad_tipo: str | None = Query(None, min_length=1, max_length=80),
    entidad_id: str | None = Query(None, min_length=1, max_length=80),
    accion: str | None = Query(None, min_length=1, max_length=80),
    actor_usuario_id: int | None = Query(None, ge=1),
    desde: datetime | None = None,
    hasta: datetime | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return AuditService(db).listar(
        entidad_tipo=entidad_tipo,
        entidad_id=entidad_id,
        accion=accion,
        actor_usuario_id=actor_usuario_id,
        desde=desde,
        hasta=hasta,
        limit=limit,
        offset=offset,
    )


@router.get("/{evento_id}", response_model=AuditEventOut)
def obtener_evento_auditoria(evento_id: int, db: Session = Depends(get_db)):
    return AuditService(db).obtener(evento_id)
