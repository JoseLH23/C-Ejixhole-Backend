"""Cabeceras de versión y aviso de compatibilidad para la API HTTP."""
from __future__ import annotations

from starlette.types import ASGIApp

from app.api import API_V1_PREFIX, LEGACY_PREFIXES


def _pertenece(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


class ApiVersioningMiddleware:
    """Identifica contratos v1 y marca las rutas históricas como deprecadas.

    No se fija todavía una fecha de retiro. Las rutas anteriores continúan
    funcionando mientras el panel, portal y futuras integraciones migran.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        es_v1 = _pertenece(path, API_V1_PREFIX)
        es_legacy = not es_v1 and any(_pertenece(path, prefix) for prefix in LEGACY_PREFIXES)

        async def send_versionado(message):
            if message["type"] == "http.response.start" and (es_v1 or es_legacy):
                headers = list(message.get("headers", []))
                headers.append((b"x-api-version", b"v1" if es_v1 else b"legacy"))

                if es_legacy:
                    successor = f"{API_V1_PREFIX}{path}"
                    headers.extend(
                        [
                            (b"deprecation", b"true"),
                            (
                                b"link",
                                f'<{successor}>; rel="successor-version"'.encode("ascii"),
                            ),
                        ]
                    )

                message = {**message, "headers": headers}

            await send(message)

        await self.app(scope, receive, send_versionado)
