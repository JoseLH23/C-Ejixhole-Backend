"""Rutas privadas del dashboard administrativo."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.dashboard import DashboardResumenOut
from app.services.dashboard_service import DashboardService
from app.services.mh_core_dashboard_service import MhCoreDashboardService

router = APIRouter(
    prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(require_roles("admin"))]
)


@router.get("/resumen", response_model=DashboardResumenOut)
def dashboard_resumen(db: Session = Depends(get_db)):
    return DashboardService(db).resumen()


@router.get("/mh-core")
def dashboard_mh_core(days: int = Query(default=7, ge=1, le=31)):
    """Intermediario seguro: la clave privada de MH-Core nunca llega al navegador."""
    return MhCoreDashboardService().obtener_dashboard(days=days)


@router.get("/mh-core/predictions")
def dashboard_mh_core_predictions(days: int = Query(default=7, ge=1, le=31)):
    """Predicciones operativas de solo lectura para administradores."""
    return MhCoreDashboardService().obtener_predicciones(days=days)


@router.get("/mh-core/predictions/evaluation")
def dashboard_mh_core_predictions_evaluation(limit: int = Query(default=12, ge=1, le=52)):
    """Historial de precisión de predicciones, sin exponer la clave privada."""
    return MhCoreDashboardService().obtener_evaluacion_predicciones(limit=limit)
