"""Observabilidad HTTP mínima sin registrar cuerpos ni datos personales."""
from __future__ import annotations

import logging
import time
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("ejixhole.http")


class RequestObservabilityMiddleware:
    """Añade un identificador por petición y registra errores del servidor."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = request.headers.get("x-request-id") or str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.perf_counter()
        status_code = 500

        async def send_with_headers(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "Error no controlado request_id=%s method=%s path=%s duration_ms=%s",
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        if status_code >= 500:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.error(
                "Respuesta crítica request_id=%s method=%s path=%s status=%s duration_ms=%s",
                request_id,
                request.method,
                request.url.path,
                status_code,
                duration_ms,
            )
