from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/status", tags=["Infraestructura"])


@router.get("")
def api_status():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_version": "v1",
        "api_prefix": "/api/v1",
    }
