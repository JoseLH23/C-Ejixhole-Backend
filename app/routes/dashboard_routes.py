"""
Rutas de Dashboard. Solo admin por ahora (ver
docs/modulos/dashboard-diseno.md sección 11 — /dashboard/caja y
/dashboard/alertas se abrirán a operador/cajero cuando se implementen,
en entregas futuras; esta entrega es solo /resumen, que sí es
estrictamente admin).

Implementado hasta ahora:
  - GET /dashboard/resumen

Pendientes (entregas futuras, mismo router):
  - GET /dashboard/ingresos
  - GET /dashboard/reservaciones
  - GET /dashboard/ocupacion
  - GET /dashboard/servicios
  - GET /dashboard/clientes
  - GET /dashboard/caja
  - GET /dashboard/alertas
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.dashboard import DashboardResumenOut
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(require_roles("admin"))]
)


@router.get("/resumen", response_model=DashboardResumenOut)
def dashboard_resumen(db: Session = Depends(get_db)):
    service = DashboardService(db)
    return service.resumen()
