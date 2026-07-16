"""Contrato v1 exclusivo para integraciones internas de solo lectura."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.service_auth import ServicePrincipal, require_mh_core_readonly
from app.database import get_db
from app.schemas.integracion_mh import MhCoreOperationalSummaryOut
from app.services.integracion_mh_service import IntegracionMhService

router = APIRouter(prefix="/integrations/mh-core", tags=["Integraciones"])


@router.get("/operational-summary", response_model=MhCoreOperationalSummaryOut)
def operational_summary(
    db: Session = Depends(get_db),
    _principal: ServicePrincipal = Depends(require_mh_core_readonly),
):
    """Entrega únicamente métricas agregadas; no expone clientes ni reservaciones."""
    return IntegracionMhService(db).resumen_operativo()
