"""Cliente servidor-a-servidor para inteligencia privada de MH-Core."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException


class MhCoreDashboardService:
    def __init__(self) -> None:
        self.base_url = os.getenv("MH_CORE_URL", "https://mh-core.onrender.com").rstrip("/")
        self.api_key = os.getenv("MH_CORE_API_KEY", "").strip()
        self.timeout_seconds = float(os.getenv("MH_CORE_TIMEOUT_SECONDS", "20"))
        environment = os.getenv("ENVIRONMENT", "production").strip().lower()
        if environment == "production" and urlparse(self.base_url).scheme != "https":
            raise RuntimeError("MH_CORE_URL debe usar HTTPS en producción.")

    def _request(self, method: str, path: str, *, params: dict[str, object], required_key: str) -> dict:
        if not self.api_key:
            raise HTTPException(status_code=503, detail="La integración con MH-Core todavía no está configurada.")
        request = Request(
            f"{self.base_url}{path}?{urlencode(params)}",
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"MH-Core respondió con estado {exc.code}.") from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(status_code=503, detail="MH-Core no está disponible temporalmente. Intenta de nuevo en unos segundos.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=502, detail="MH-Core devolvió una respuesta inesperada.") from exc
        if not isinstance(payload, dict) or required_key not in payload:
            raise HTTPException(status_code=502, detail="MH-Core devolvió una respuesta inesperada.")
        return payload

    def _get(self, path: str, *, params: dict[str, object], required_key: str) -> dict:
        return self._request("GET", path, params=params, required_key=required_key)

    def obtener_dashboard(self, *, days: int = 7) -> dict:
        return self._get("/integrations/ejixhole/executive-dashboard", params={"days": days}, required_key="kpis")

    def obtener_predicciones(self, *, days: int = 7) -> dict:
        return self._get("/integrations/ejixhole/predictions", params={"days": days}, required_key="predictions")

    def obtener_evaluacion_predicciones(self, *, limit: int = 12) -> dict:
        return self._get("/integrations/ejixhole/predictions/evaluation", params={"limit": limit}, required_key="evaluations")

    def obtener_centro_decisiones(self, *, limit: int = 50) -> dict:
        return self._get("/integrations/ejixhole/decisions", params={"limit": limit}, required_key="items")

    def obtener_ingresos_por_servicio(self, *, days: int = 30) -> dict:
        return self._get("/integrations/ejixhole/profitability", params={"days": days}, required_key="services")

    @staticmethod
    def _recommendation_path(code: str, suffix: str) -> str:
        return f"/integrations/ejixhole/predictions/recommendations/{quote(code, safe='')}/{suffix}"

    def decidir_recomendacion(self, *, business_date: str, code: str, decision: str) -> dict:
        return self._request("POST", self._recommendation_path(code, "decision"), params={"business_date": business_date, "decision": decision}, required_key="decision")

    def registrar_resultado(self, *, business_date: str, code: str, outcome: str, note: str | None = None) -> dict:
        params: dict[str, object] = {"business_date": business_date, "outcome": outcome}
        if note:
            params["note"] = note
        return self._request("POST", self._recommendation_path(code, "outcome"), params=params, required_key="outcome")
