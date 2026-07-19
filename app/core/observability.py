"""Observabilidad HTTP sin registrar cuerpos, consultas ni datos personales."""
from __future__ import annotations

import json
import logging
import re
import time
from uuid import uuid4

from starlette.requests import Request
from starlette.types import ASGIApp

from app.core.metrics import http_metrics

logger = logging.getLogger("ejixhole.http")
_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}$")
_INTEGER = re.compile(r"^\d+$")


def _safe_path(path: str) -> str:
    parts = []
    for segment in path.split("/"):
        if _INTEGER.fullmatch(segment):
            parts.append("{id}")
        elif _UUID.fullmatch(segment):
            parts.append("{uuid}")
        else:
            parts.append(segment[:80])
    return "/".join(parts)[:500]


def _log(level: int, event: str, **fields) -> None:
    logger.log(level, json.dumps({"event": event, **fields}, ensure_ascii=False, sort_keys=True))


class RequestObservabilityMiddleware:
    """Correlaciona peticiones, mide latencia y registra el resultado seguro."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = request.headers.get("x-request-id") or str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        safe_path = _safe_path(request.url.path)
        started = time.perf_counter()
        status_code = 500
        http_metrics.begin()

        async def send_with_headers(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii", errors="ignore")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            duration_ms = int((time.perf_counter() - started) * 1000)
            http_metrics.finish(500, duration_ms)
            _log(
                logging.ERROR,
                "http.unhandled_error",
                request_id=request_id,
                method=request.method,
                path=safe_path,
                status=500,
                duration_ms=duration_ms,
            )
            logger.exception("Excepción HTTP no controlada request_id=%s", request_id)
            raise

        duration_ms = int((time.perf_counter() - started) * 1000)
        http_metrics.finish(status_code, duration_ms)
        level = logging.ERROR if status_code >= 500 else logging.WARNING if status_code >= 400 else logging.INFO
        _log(
            level,
            "http.response",
            request_id=request_id,
            method=request.method,
            path=safe_path,
            status=status_code,
            duration_ms=duration_ms,
        )
