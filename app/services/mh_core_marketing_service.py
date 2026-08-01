"""Intermediario seguro entre el panel administrativo y MindHigh/MH-Core."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException


class MhCoreMarketingService:
    SERVICE_ID = "ejixhole-backend"

    def __init__(self) -> None:
        self.base_url = os.getenv("MH_CORE_URL", "https://mh-core.onrender.com").rstrip("/")
        self.api_key = os.getenv("MH_CORE_SERVICE_KEY", "").strip()
        self.timeout_seconds = float(os.getenv("MH_CORE_TIMEOUT_SECONDS", "20"))
        environment = os.getenv("ENVIRONMENT", "production").strip().lower()
        if environment == "production" and urlparse(self.base_url).scheme != "https":
            raise RuntimeError("MH_CORE_URL debe usar HTTPS en producción.")

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
    ) -> dict:
        if not self.api_key:
            raise HTTPException(
                status_code=503,
                detail="La integración con Marketing todavía no está configurada.",
            )

        data = None
        headers = {
            "X-Service-ID": self.SERVICE_ID,
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise HTTPException(
                    status_code=503,
                    detail="La conexión privada con Marketing no está autorizada.",
                ) from exc
            if exc.code == 422:
                raise HTTPException(
                    status_code=422,
                    detail="La campaña contiene información no autorizada o incompleta.",
                ) from exc
            raise HTTPException(
                status_code=502,
                detail=f"MH-Core respondió con estado {exc.code}.",
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(
                status_code=503,
                detail="Marketing no está disponible temporalmente.",
            ) from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=502,
                detail="MH-Core devolvió una respuesta inesperada.",
            ) from exc

        if not isinstance(result, dict):
            raise HTTPException(
                status_code=502,
                detail="MH-Core devolvió una respuesta inesperada.",
            )
        return result

    def obtener_estado(self) -> dict:
        if not self.api_key:
            return {
                "configured": False,
                "available": False,
                "knowledge_version": None,
                "documents": 0,
                "message": "El módulo está preparado, pero MH-Core todavía no está configurado.",
            }

        try:
            result = self._request("GET", "/mindhigh/marketing/status")
        except HTTPException as exc:
            return {
                "configured": True,
                "available": False,
                "knowledge_version": None,
                "documents": 0,
                "message": exc.detail if isinstance(exc.detail, str) else "Marketing no está disponible.",
            }

        available = result.get("available") is True
        return {
            "configured": True,
            "available": available,
            "knowledge_version": result.get("knowledge_version") if available else None,
            "documents": int(result.get("documents") or 0) if available else 0,
            "message": (
                "Marketing está listo para generar borradores."
                if available
                else "MH-Core está conectado, pero el conocimiento aprobado todavía no está disponible."
            ),
        }

    def crear_borrador(self, brief: dict) -> dict:
        result = self._request(
            "POST",
            "/mindhigh/marketing/campaigns/draft",
            payload=brief,
        )
        required = {
            "name",
            "knowledge_version",
            "knowledge_citations",
            "requires_human_approval",
            "contents",
        }
        if not required.issubset(result):
            raise HTTPException(
                status_code=502,
                detail="MH-Core devolvió una campaña incompleta.",
            )
        return result
