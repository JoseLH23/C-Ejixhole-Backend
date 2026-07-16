"""Monitoreo sintético de los servicios públicos de EjiXhole.

No usa credenciales ni modifica datos. Comprueba disponibilidad HTTP, que las
aplicaciones web entreguen su shell React y que el backend tenga acceso a
PostgreSQL y configuración de notificaciones.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class Target:
    name: str
    url: str
    validator: Callable[[bytes], str]


@dataclass(frozen=True)
class CheckResult:
    name: str
    url: str
    ok: bool
    latency_ms: int
    detail: str


def _validate_backend(body: bytes) -> str:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("el backend no devolvió JSON válido") from exc

    if payload.get("status") != "ready":
        raise ValueError(f"estado inesperado: {payload.get('status')!r}")

    checks = payload.get("checks") or {}
    if checks.get("database") != "up":
        raise ValueError("PostgreSQL no está disponible")
    if checks.get("notifications") != "configured":
        raise ValueError("las notificaciones no están configuradas")

    return "API, PostgreSQL y configuración de notificaciones disponibles"


def _validate_react_app(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace").lower()
    if 'id="root"' not in text and "id='root'" not in text:
        raise ValueError("la respuesta no contiene el contenedor React esperado")
    return "aplicación web disponible"


def _targets() -> list[Target]:
    return [
        Target(
            "Backend",
            os.getenv(
                "BACKEND_HEALTH_URL",
                "https://c-ejixhole-backend.onrender.com/health/ready",
            ),
            _validate_backend,
        ),
        Target(
            "Portal público",
            os.getenv("PORTAL_URL", "https://ejixhole-reservas.vercel.app/"),
            _validate_react_app,
        ),
        Target(
            "Panel administrativo",
            os.getenv("ADMIN_URL", "https://ejixhole-frontend.vercel.app/"),
            _validate_react_app,
        ),
    ]


def _check_once(target: Target, timeout: int) -> CheckResult:
    started = time.perf_counter()
    request = Request(
        target.url,
        headers={
            "User-Agent": "EjiXhole-Production-Monitor/1.0",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
        },
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.getcode()
            body = response.read(1_000_000)
    except HTTPError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        return CheckResult(target.name, target.url, False, latency, f"HTTP {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        latency = int((time.perf_counter() - started) * 1000)
        return CheckResult(target.name, target.url, False, latency, str(exc))

    latency = int((time.perf_counter() - started) * 1000)
    if not 200 <= status < 300:
        return CheckResult(target.name, target.url, False, latency, f"HTTP {status}")

    try:
        detail = target.validator(body)
    except ValueError as exc:
        return CheckResult(target.name, target.url, False, latency, str(exc))

    return CheckResult(target.name, target.url, True, latency, detail)


def check_with_retries(target: Target, attempts: int, timeout: int, delay: int) -> CheckResult:
    result: CheckResult | None = None
    for attempt in range(1, attempts + 1):
        result = _check_once(target, timeout)
        if result.ok:
            return result
        if attempt < attempts:
            print(
                f"Reintento {attempt}/{attempts - 1} para {target.name}: {result.detail}",
                flush=True,
            )
            time.sleep(delay)

    assert result is not None
    return result


def _markdown(results: list[CheckResult]) -> str:
    lines = ["# Monitoreo de producción EjiXhole", ""]
    for result in results:
        icon = "✅" if result.ok else "❌"
        lines.append(
            f"- {icon} **{result.name}** — {result.detail} "
            f"({result.latency_ms} ms)"
        )
    lines.append("")
    lines.append(
        "La comprobación de correo valida su configuración; no envía mensajes "
        "sintéticos para evitar spam."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    attempts = max(1, int(os.getenv("MONITOR_ATTEMPTS", "4")))
    timeout = max(1, int(os.getenv("MONITOR_TIMEOUT_SECONDS", "45")))
    delay = max(0, int(os.getenv("MONITOR_RETRY_DELAY_SECONDS", "15")))

    results = [
        check_with_retries(target, attempts=attempts, timeout=timeout, delay=delay)
        for target in _targets()
    ]
    report = _markdown(results)
    print(report)

    report_path = Path(os.getenv("MONITOR_REPORT_PATH", "monitor-report.md"))
    report_path.write_text(report, encoding="utf-8")

    github_summary = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary:
        with Path(github_summary).open("a", encoding="utf-8") as summary:
            summary.write(report)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
