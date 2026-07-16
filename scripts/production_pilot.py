"""Checklist no destructivo previo a un piloto operativo de producción.

Este script únicamente consulta servicios públicos. No inicia sesión, no crea
reservaciones y no modifica datos. El recorrido real permanece como una lista
manual que debe ejecutar una persona autorizada desde el panel.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ReadinessError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReadinessConfig:
    backend_url: str
    portal_url: str
    admin_url: str


def _join(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _request(method: str, url: str, timeout: int = 60) -> tuple[int, bytes]:
    request = Request(
        url,
        method=method,
        headers={
            "User-Agent": "EjiXhole-Production-Readiness/1.0",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.getcode(), response.read(1_000_000)
    except HTTPError as exc:
        raise ReadinessError(f"{url} devolvió HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ReadinessError(f"{url} no respondió: {exc}") from exc


def _json(url: str) -> Any:
    status, body = _request("GET", url)
    if not 200 <= status < 300:
        raise ReadinessError(f"{url}: HTTP {status}")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReadinessError(f"{url} no devolvió JSON válido") from exc


def _verificar_shell(nombre: str, url: str) -> str:
    status, body = _request("GET", url)
    if not 200 <= status < 300:
        raise ReadinessError(f"{nombre}: HTTP {status}")
    html = body.decode("utf-8", errors="replace").lower()
    if 'id="root"' not in html and "id='root'" not in html:
        raise ReadinessError(f"{nombre}: no contiene el contenedor React")
    return f"{nombre} disponible"


def verificar_despliegues(config: ReadinessConfig) -> list[str]:
    resultados: list[str] = []

    health = _json(_join(config.backend_url, "/health/ready"))
    checks = health.get("checks") or {}
    if health.get("status") != "ready" or checks.get("database") != "up":
        raise ReadinessError("Backend o PostgreSQL no están listos")
    if checks.get("notifications") != "configured":
        raise ReadinessError("Las notificaciones de producción no están configuradas")
    resultados.append("Backend, PostgreSQL y notificaciones listos")

    resultados.append(_verificar_shell("Portal público", config.portal_url))
    resultados.append(_verificar_shell("Panel administrativo", config.admin_url))

    servicios = _json(_join(config.backend_url, "/publico/servicios"))
    if not isinstance(servicios, list) or not servicios:
        raise ReadinessError("El catálogo público no devolvió servicios")
    resultados.append(f"Catálogo público disponible ({len(servicios)} servicios)")

    hoy = __import__("datetime").date.today().isoformat()
    bloqueos_url = _join(config.backend_url, "/publico/fechas-bloqueadas")
    bloqueos = _json(f"{bloqueos_url}?desde={hoy}&hasta={hoy}")
    if not isinstance(bloqueos, list):
        raise ReadinessError("La disponibilidad pública no devolvió una lista válida")
    resultados.append("Consulta pública de disponibilidad operativa")
    return resultados


def _config_desde_entorno() -> ReadinessConfig:
    return ReadinessConfig(
        backend_url=os.getenv(
            "BACKEND_URL", "https://c-ejixhole-backend.onrender.com"
        ).rstrip("/"),
        portal_url=os.getenv(
            "PORTAL_URL", "https://ejixhole-reservas.vercel.app/"
        ),
        admin_url=os.getenv(
            "ADMIN_URL", "https://ejixhole-frontend.vercel.app/"
        ),
    )


def _escribir_reporte(resultados: list[str]) -> str:
    lines = ["# Preparación para piloto de producción", ""]
    lines.extend(f"- ✅ {resultado}" for resultado in resultados)
    lines.extend(
        [
            "",
            "## Resultado",
            "",
            "Los servicios públicos están listos para que una persona autorizada "
            "ejecute el checklist operativo manual desde el panel.",
            "",
            "Este proceso no creó ni modificó datos de producción.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        resultados = verificar_despliegues(_config_desde_entorno())
        reporte = _escribir_reporte(resultados)
        print(reporte)
        Path(os.getenv("PILOT_REPORT_PATH", "production-pilot-report.md")).write_text(
            reporte, encoding="utf-8"
        )
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as output:
                output.write(reporte)
        return 0
    except ReadinessError as exc:
        print(f"CHECKLIST BLOQUEADO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
