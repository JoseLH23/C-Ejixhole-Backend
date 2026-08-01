"""Intermediario seguro entre el panel administrativo y MindHigh/MH-Core."""
from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.mh_core_client_auth import cabeceras_mh_core, obtener_credencial_mh_core
from app.schemas.marketing import MarketingCampaignOut


_RETRYABLE_UPSTREAM_STATUS = {502, 503, 504}
_TRANSIENT_STATUS_DETAILS = {
    "MH-Core respondió con estado 502.",
    "MH-Core respondió con estado 503.",
    "MH-Core respondió con estado 504.",
    "Marketing no está disponible temporalmente.",
}
_INITIAL_RETRY_DELAY_SECONDS = 1.0
_MAX_RETRY_DELAY_SECONDS = 8.0
_MAX_ATTEMPT_TIMEOUT_SECONDS = 20.0
_STATUS_TOTAL_TIMEOUT_SECONDS = 4.0
_WAKE_TIMEOUT_SECONDS = 1.5


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


def _abrir_con_reintentos(request: Request, total_timeout: float):
    """Tolera errores temporales sin reintentar autenticación ni validación."""
    deadline = time.monotonic() + total_timeout
    retry_delay = _INITIAL_RETRY_DELAY_SECONDS
    last_error: HTTPError | URLError | TimeoutError | None = None

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        attempt_timeout = max(1.0, min(_MAX_ATTEMPT_TIMEOUT_SECONDS, remaining))

        try:
            return urlopen(request, timeout=attempt_timeout)
        except HTTPError as exc:
            if exc.code not in _RETRYABLE_UPSTREAM_STATUS:
                raise
            last_error = exc
            exc.close()
        except (URLError, TimeoutError) as exc:
            last_error = exc

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(retry_delay, remaining))
        retry_delay = min(retry_delay * 2, _MAX_RETRY_DELAY_SECONDS)

    if last_error is not None:
        raise last_error
    raise TimeoutError("Se agotó el tiempo de conexión con Marketing.")


class MhCoreMarketingService:
    def __init__(self) -> None:
        self.base_url = os.getenv("MH_CORE_URL", "https://mh-core.onrender.com").rstrip("/")
        self.credential = obtener_credencial_mh_core()
        self.timeout_seconds = _marketing_timeout_seconds()
        environment = os.getenv("ENVIRONMENT", "production").strip().lower()
        if environment == "production" and urlparse(self.base_url).scheme != "https":
            raise RuntimeError("MH_CORE_URL debe usar HTTPS en producción.")

    def _despertar_servicio(self) -> None:
        """Dispara el arranque de Render sin bloquear una función de Vercel."""
        request = Request(
            f"{self.base_url}/health/live",
            headers={"User-Agent": "Ejixhole-Backend/Marketing-Wakeup"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=_WAKE_TIMEOUT_SECONDS):
                return
        except (HTTPError, URLError, TimeoutError):
            # El primer intento puede terminar en timeout/502 mientras Render despierta.
            # Haber enviado la solicitud es suficiente; el panel volverá a consultar.
            return

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict | None = None,
        total_timeout: float | None = None,
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
            with _abrir_con_reintentos(
                request,
                total_timeout if total_timeout is not None else self.timeout_seconds,
            ) as response:
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

    @staticmethod
    def _es_arranque_temporal(exc: HTTPException) -> bool:
        return isinstance(exc.detail, str) and exc.detail in _TRANSIENT_STATUS_DETAILS

    def obtener_estado(self) -> dict:
        if self.credential is None:
            return {
                "configured": False,
                "available": False,
                "warming_up": False,
                "knowledge_version": None,
                "documents": 0,
                "message": "El módulo está preparado, pero MH-Core todavía no está configurado.",
            }

        self._despertar_servicio()
        try:
            result = self._request(
                "GET",
                "/mindhigh/marketing/status",
                total_timeout=min(_STATUS_TOTAL_TIMEOUT_SECONDS, self.timeout_seconds),
            )
        except HTTPException as exc:
            warming_up = self._es_arranque_temporal(exc)
            return {
                "configured": True,
                "available": False,
                "warming_up": warming_up,
                "knowledge_version": None,
                "documents": 0,
                "message": (
                    "Marketing está despertando. Esta pantalla se actualizará automáticamente."
                    if warming_up
                    else exc.detail
                    if isinstance(exc.detail, str)
                    else "Marketing no está disponible."
                ),
            }

        available = result.get("available") is True
        return {
            "configured": True,
            "available": available,
            "warming_up": False,
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
