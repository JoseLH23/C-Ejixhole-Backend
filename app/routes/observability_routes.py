"""Resumen privado de salud, métricas de proceso y objetivos SLO."""
from __future__ import annotations

from datetime import datetime, timezone
import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.metrics import http_metrics
from app.database import get_db
from app.dependencies import require_roles

router = APIRouter(
    prefix="/observabilidad",
    tags=["Observabilidad"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("/resumen")
def observability_summary(db: Session = Depends(get_db)):
    started = time.perf_counter()
    database_status = "up"
    try:
        db.execute(text("SELECT 1"))
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
