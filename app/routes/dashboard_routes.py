"""Rutas privadas del dashboard administrativo."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.schemas.dashboard import DashboardResumenOut
from app.services.dashboard_service import DashboardService
from app.services.mh_core_dashboard_service import MhCoreDashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(require_roles("admin"))])


@router.get("/resumen", response_model=DashboardResumenOut)
def dashboard_resumen(db: Session = Depends(get_db)):
    return DashboardService(db).resumen()


@router.get("/mh-core")
def dashboard_mh_core(days: int = Query(default=7, ge=1, le=31)):
    return MhCoreDashboardService().obtener_dashboard(days=days)


@router.get("/mh-core/predictions")
def dashboard_mh_core_predictions(days: int = Query(default=7, ge=1, le=31)):
    return MhCoreDashboardService().obtener_predicciones(days=days)


@router.get("/mh-core/predictions/evaluation")
def dashboard_mh_core_predictions_evaluation(limit: int = Query(default=12, ge=1, le=52)):
    return MhCoreDashboardService().obtener_evaluacion_predicciones(limit=limit)


@router.get("/mh-core/decisions")
def dashboard_mh_core_decisions(limit: int = Query(default=50, ge=1, le=200)):
    return MhCoreDashboardService().obtener_centro_decisiones(limit=limit)


@router.get("/mh-core/profitability")
def dashboard_mh_core_profitability(days: int = Query(default=30, ge=1, le=365)):
    return MhCoreDashboardService().obtener_ingresos_por_servicio(days=days)


@router.post("/mh-core/predictions/recommendations/{code}/decision")
def dashboard_mh_core_recommendation_decision(code: str, business_date: str, decision: str):
    return MhCoreDashboardService().decidir_recomendacion(business_date=business_date, code=code, decision=decision)


@router.post("/mh-core/predictions/recommendations/{code}/outcome")
def dashboard_mh_core_recommendation_outcome(code: str, business_date: str, outcome: str, note: str | None = Query(default=None, max_length=500)):
    return MhCoreDashboardService().registrar_resultado(business_date=business_date, code=code, outcome=outcome, note=note)
