"""Autenticación exclusiva para disparar lotes del outbox sin un worker pagado."""
from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException, status


def require_outbox_dispatch_key(
    x_outbox_dispatch_key: str | None = Header(
        default=None,
        alias="X-Outbox-Dispatch-Key",
    ),
) -> None:
    expected = os.getenv("OUTBOX_DISPATCH_KEY", "").strip()
    if len(expected) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El disparador seguro del outbox no está configurado.",
        )
    if not x_outbox_dispatch_key or not hmac.compare_digest(
        x_outbox_dispatch_key.encode("utf-8"),
        expected.encode("utf-8"),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial del disparador de outbox inválida o faltante.",
        )
