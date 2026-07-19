"""Extensión del dashboard para consultar la salud operativa de MH-Core."""
from fastapi import APIRouter

from app.services.mh_core_dashboard_service import MhCoreDashboardService

router = APIRouter()


@router.get("/mh-core/observability")
def mh_core_observability():
    return MhCoreDashboardService().obtener_observabilidad()
