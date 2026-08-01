"""Intermediario seguro entre el panel administrativo y MindHigh/MH-Core."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.mh_core_client_auth import cabeceras_mh_core, obtener_credencial_mh_core
from app.schemas.marketing import MarketingCampaignOut


def _marketing_timeout_seconds() -> float:
    raw = os.getenv(
        "MH_CORE_MARKETING_TIMEOUT_SECONDS",
        os.getenv("MH_CORE_TIMEOUT_SECONDS", "75"),
    )
    try:
        timeout = float(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("MH_CORE_MARKETING_TIMEOUT_SECONDS debe ser numérico.") from exc
    if not 1 <= timeout <= 120:
        raise RuntimeError("MH_CORE_MARKETING_TIMEOUT_SECONDS debe estar entre 1 y 120 segundos.")
    return timeout


class MhCoreMarketingService:
    def __init__(self) -> None:
        self.base_url = os.getenv("MH_CORE_URL", "https://mh-core.onrender.com").rstrip("/")
        self.credential = obtener_credencial_mh_core()
        self.timeout_seconds = _marketing_timeout_seconds()
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
        if self.credential is None:
            raise HTTPException(
                status_code=503,
                detail="La integración con Marketing todavía no está configurada.",
            )

        data = None
        headers = cabeceras_mh_core(self.credential)
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
        if self.credential is None:
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
        try:
            campaign = MarketingCampaignOut.model_validate(result)
        except ValidationError as exc:
            raise HTTPException(
                status_code=502,
                detail="MH-Core devolvió una campaña incompleta.",
            ) from exc
        return campaign.model_dump(mode="json")
