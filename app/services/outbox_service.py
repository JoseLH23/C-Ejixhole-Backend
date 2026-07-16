"""Registro transaccional de eventos de dominio en la bandeja de salida."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.outbox_event import OutboxEvent


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class OutboxService:
    """Agrega eventos a la misma sesión SQLAlchemy de la operación de negocio.

    No hace commit por su cuenta. El evento y el cambio de negocio se confirman o
    revierten juntos, evitando perder eventos entre dos transacciones separadas.
    """

    @staticmethod
    def record(
        db: Session,
        *,
        event_key: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: int | str,
        payload: dict[str, Any],
        schema_version: int = 1,
    ) -> OutboxEvent:
        event = OutboxEvent(
            event_key=event_key,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=str(aggregate_id),
            schema_version=schema_version,
            payload=_json_safe(payload),
        )
        db.add(event)
        db.flush()
        return event
