"""Cliente servidor-a-servidor para el dashboard ejecutivo privado de MH-Core."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status


class MhCoreDashboardService:
    def __init__(self) -> None:
        self.base_url = os.getenv("MH_CORE_URL", "https://mh-core.onrender.com").rstrip("/")
        self.api_key = os.getenv("MH_CORE_API_KEY", "").strip()
        self.timeout_seconds = float(os.getenv("MH_CORE_TIMEOUT_SECONDS", "20"))

    def obtener_dashboard(self, *, days: int = 7) -> dict:
        if not self.api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="La integración con MH-Core todavía no está configurada.",
            )

        query = urlencode({"days": days})
        request = Request(
            f"{self.base_url}/integrations/ejixhole/executive-dashboard?{query}",
            headers={"X-API-Key": self.api_key, "Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"MH-Core respondió con estado {exc.code}.",
            ) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MH-Core no está disponible temporalmente. Intenta de nuevo en unos segundos.",
            ) from exc

        if not isinstance(payload, dict) or "kpis" not in payload:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="MH-Core devolvió una respuesta inesperada.",
            )
        return payload
