"""Resumen privado de salud, métricas de proceso y objetivos SLO."""
from __future__ import annotations

from datetime import datetime, timezone
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import text

from app.core.metrics import http_metrics
from app.core.security import decode_access_token
from app.database import engine
from app.dependencies import _token_de_request, oauth2_scheme


async def require_diagnostic_admin(
    request: Request,
    token_bearer: str | None = Depends(oauth2_scheme),
) -> dict:
    """Valida el JWT firmado sin consultar la base diagnosticada.

    Esta excepción arquitectónica se limita a un endpoint GET de solo lectura.
    Las rutas de negocio siguen comprobando usuario activo y rol en PostgreSQL.
    """
    token = _token_de_request(request, token_bearer)
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas o sesión expirada.",
        ) from exc
    if payload.get("rol") != "admin" or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere una sesión administrativa para consultar diagnósticos.",
        )
    return payload


router = APIRouter(
    prefix="/observabilidad",
    tags=["Observabilidad"],
    dependencies=[Depends(require_diagnostic_admin)],
)


@router.get("/resumen")
def observability_summary():
    started = time.perf_counter()
    database_status = "up"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        database_status = "down"
    database_latency_ms = int((time.perf_counter() - started) * 1000)

    metrics = http_metrics.snapshot()
    checks = {
        "database": database_status == "up",
        "http_slo": metrics["slo"]["status"] == "healthy",
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "healthy" if all(checks.values()) else "degraded",
        "checks": checks,
        "dependencies": {
            "database": {
                "status": database_status,
                "latency_ms": database_latency_ms,
            }
        },
        "http": metrics,
    }
