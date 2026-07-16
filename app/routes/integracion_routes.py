"""Contratos v1 exclusivos para integraciones internas y su diagnóstico."""
from dataclasses import asdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.outbox_dispatch_auth import require_outbox_dispatch_key
from app.core.service_auth import ServicePrincipal, require_mh_core_readonly
from app.database import get_db
from app.dependencies import require_roles
from app.schemas.integracion_mh import MhCoreOperationalSummaryOut
from app.schemas.outbox_status import OutboxChannelStatusOut, OutboxEventStatusOut
from app.services.integracion_mh_service import IntegracionMhService
from app.services.outbox_publisher_service import OutboxPublisher
from app.services.outbox_status_service import OutboxStatusService

router = APIRouter(prefix="/integrations/mh-core", tags=["Integraciones"])


@router.get("/operational-summary", response_model=MhCoreOperationalSummaryOut)
def operational_summary(
    db: Session = Depends(get_db),
    _principal: ServicePrincipal = Depends(require_mh_core_readonly),
):
    """Entrega únicamente métricas agregadas; no expone clientes ni reservaciones."""
    return IntegracionMhService(db).resumen_operativo()


@router.get(
    "/outbox/status",
    response_model=OutboxChannelStatusOut,
    dependencies=[Depends(require_roles("admin"))],
)
def outbox_status(db: Session = Depends(get_db)):
    """Diagnóstico administrativo sin payloads, claves ni datos personales."""
    return OutboxStatusService(db).status()


@router.get(
    "/outbox/events/{event_id}",
    response_model=OutboxEventStatusOut,
    dependencies=[Depends(require_roles("admin"))],
)
def outbox_event_status(event_id: UUID, db: Session = Depends(get_db)):
    """Confirma el estado de entrega de un UUID específico."""
    event = OutboxStatusService(db).event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento no encontrado en el outbox.")
    return event


@router.post(
    "/outbox/publish",
    dependencies=[Depends(require_outbox_dispatch_key)],
)
def publish_outbox_batch():
    """Publica un solo lote; pensado para cron externo gratuito o ejecución manual."""
    return asdict(OutboxPublisher().publish_once())
