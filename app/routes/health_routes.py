"""Endpoints públicos y mínimos para monitoreo operativo.

`/health/live` confirma que el proceso HTTP está vivo.
`/health/ready` comprueba que la API puede comunicarse con PostgreSQL y
reporta, sin exponer secretos, si las notificaciones están configuradas.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Monitoreo"])


def _notificaciones_configuradas() -> bool:
    resend = bool(
        settings.RESEND_API_KEY
        and settings.RESEND_FROM_EMAIL
        and settings.NOTIFICACIONES_EMAIL_DESTINO
    )
    smtp = bool(
        settings.SMTP_HOST
        and settings.SMTP_USER
        and settings.SMTP_PASSWORD
        and settings.NOTIFICACIONES_EMAIL_DESTINO
    )
    return resend or smtp


@router.get("/live")
def liveness() -> dict:
    """No toca dependencias externas; sirve para saber si el proceso vive."""
    return {
        "status": "alive",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@router.get("/ready")
def readiness(db: Session = Depends(get_db)):
    """Confirma acceso a PostgreSQL sin filtrar detalles de conexión."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # frontera de monitoreo: cualquier fallo implica no disponible
        logger.exception("Readiness check: PostgreSQL no está disponible")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "service": settings.PROJECT_NAME,
                "version": settings.VERSION,
                "checks": {
                    "database": "down",
                    "notifications": (
                        "configured" if _notificaciones_configuradas() else "not_configured"
                    ),
                },
            },
        )

    return {
        "status": "ready",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "checks": {
            "database": "up",
            "notifications": (
                "configured" if _notificaciones_configuradas() else "not_configured"
            ),
        },
    }
