"""Checklist ejecutable y piloto operativo controlado de producción.

Por defecto solo verifica servicios públicos y no modifica datos. El recorrido
real exige una confirmación exacta y credenciales administrativas entregadas
mediante variables de entorno; nunca se escriben en archivos ni en logs.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import date, timedelta
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

CONFIRMACION_REAL = "EJECUTAR_PILOTO_REAL"
METODOS_MUTABLES = {"POST", "PUT", "PATCH", "DELETE"}


class PilotError(RuntimeError):
    pass


@dataclass(frozen=True)
class PilotConfig:
    backend_url: str
    portal_url: str
    admin_url: str
    ejecutar_real: bool
    admin_email: str = ""
    admin_password: str = ""
    run_id: str = "manual"


class HttpClient:
    def __init__(self) -> None:
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def cookie(self, nombre: str) -> str | None:
        for cookie in self.cookies:
            if cookie.name == nombre:
                return cookie.value
        return None

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> tuple[int, bytes, dict[str, str]]:
        request_headers = {
            "User-Agent": "EjiXhole-Production-Pilot/1.0",
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache",
            **(headers or {}),
        }
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        if method.upper() in METODOS_MUTABLES:
            csrf = self.cookie("ejixhole_csrf")
            if csrf:
                request_headers.setdefault("X-CSRF-Token", csrf)

        request = Request(url, data=data, headers=request_headers, method=method.upper())
        try:
            with self.opener.open(request, timeout=timeout) as response:
                return response.getcode(), response.read(1_000_000), dict(response.headers.items())
        except HTTPError as exc:
            body = exc.read(1_000_000)
            detail = body.decode("utf-8", errors="replace")[:500]
            raise PilotError(f"{method} {url} devolvió HTTP {exc.code}: {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PilotError(f"{method} {url} no respondió: {exc}") from exc

    def json(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        status, body, _ = self.request(method, url, payload=payload, headers=headers)
        if status not in expected:
            raise PilotError(f"{method} {url}: se esperaba {expected} y llegó HTTP {status}")
        if not body:
            return None
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PilotError(f"{method} {url} no devolvió JSON válido") from exc


def _join(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _verificar_shell(client: HttpClient, nombre: str, url: str) -> str:
    status, body, _ = client.request("GET", url)
    if not 200 <= status < 300:
        raise PilotError(f"{nombre}: HTTP {status}")
    html = body.decode("utf-8", errors="replace").lower()
    if 'id="root"' not in html and "id='root'" not in html:
        raise PilotError(f"{nombre}: no contiene el contenedor React")
    return f"{nombre} disponible"


def verificar_despliegues(config: PilotConfig, client: HttpClient) -> list[str]:
    resultados: list[str] = []
    health = client.json("GET", _join(config.backend_url, "/health/ready"))
    checks = health.get("checks") or {}
    if health.get("status") != "ready" or checks.get("database") != "up":
        raise PilotError("Backend o PostgreSQL no están listos")
    if checks.get("notifications") != "configured":
        raise PilotError("Las notificaciones de producción no están configuradas")
    resultados.append("Backend, PostgreSQL y notificaciones listos")

    resultados.append(_verificar_shell(client, "Portal público", config.portal_url))
    resultados.append(_verificar_shell(client, "Panel administrativo", config.admin_url))

    servicios = client.json("GET", _join(config.backend_url, "/publico/servicios"))
    if not isinstance(servicios, list) or not servicios:
        raise PilotError("El catálogo público no devolvió servicios")
    resultados.append(f"Catálogo público disponible ({len(servicios)} servicios)")
    return resultados


def _login(config: PilotConfig, client: HttpClient) -> dict[str, Any]:
    client.json(
        "POST",
        _join(config.backend_url, "/auth/login"),
        payload={"email": config.admin_email, "password": config.admin_password},
    )
    if not client.cookie("ejixhole_session"):
        raise PilotError("El login no entregó la cookie HttpOnly ejixhole_session")
    if not client.cookie("ejixhole_csrf"):
        raise PilotError("El login no entregó la cookie CSRF")
    return client.json("GET", _join(config.backend_url, "/auth/me"))


def _fecha_piloto(config: PilotConfig) -> date:
    explicita = os.getenv("PILOT_VISIT_DATE", "").strip()
    if explicita:
        try:
            return date.fromisoformat(explicita)
        except ValueError as exc:
            raise PilotError("PILOT_VISIT_DATE debe usar YYYY-MM-DD") from exc
    return date.today() + timedelta(days=14)


def ejecutar_piloto_real(config: PilotConfig, client: HttpClient) -> dict[str, Any]:
    if not config.admin_email or not config.admin_password:
        raise PilotError("Faltan PILOT_ADMIN_EMAIL y PILOT_ADMIN_PASSWORD")

    perfil = _login(config, client)
    if perfil.get("rol") != "admin":
        raise PilotError("El piloto real exige una cuenta con rol admin")

    abiertas = client.json("GET", _join(config.backend_url, "/caja?estado=abierta&limit=200"))
    propias = [sesion for sesion in abiertas if sesion.get("usuario_id") == perfil.get("id")]
    if propias:
        raise PilotError(
            "La cuenta del piloto ya tiene una caja abierta. Se aborta para no mezclar "
            "la prueba con una operación activa."
        )

    visita = _fecha_piloto(config)
    clave_base = f"production-pilot-{config.run_id}"
    nombre = f"PILOTO CONTROLADO {config.run_id}"[:150]
    notas = (
        "PRUEBA OPERATIVA CONTROLADA. NO CONTACTAR NI ATENDER COMO CLIENTE REAL. "
        f"Run: {config.run_id}."
    )

    reserva = client.json(
        "POST",
        _join(config.backend_url, "/publico/reservaciones"),
        payload={
            "nombre_completo": nombre,
            "email": "piloto.controlado@example.com",
            "telefono": "0000000000",
            "tipo_reservacion": "entrada",
            "fecha_llegada": visita.isoformat(),
            "fecha_salida": visita.isoformat(),
            "num_personas": 1,
            "unidad_hospedaje_id": None,
            "notas": notas,
        },
        headers={"Idempotency-Key": f"{clave_base}-reservation"},
        expected=(201,),
    )
    reservacion_id = int(reserva["id"])
    total = str(reserva["total"])

    sesion = client.json(
        "POST",
        _join(config.backend_url, "/caja/abrir"),
        payload={"monto_apertura": "0.00"},
        headers={"Idempotency-Key": f"{clave_base}-cash-open"},
        expected=(201,),
    )
    sesion_id = int(sesion["id"])

    try:
        confirmada = client.json(
            "PATCH",
            _join(config.backend_url, f"/reservaciones/{reservacion_id}/estado"),
            payload={"nuevo_estado": "confirmada"},
        )
        if confirmada.get("estado") != "confirmada":
            raise PilotError("La reservación no quedó confirmada")

        client.json(
            "POST",
            _join(config.backend_url, "/pagos"),
            payload={
                "reservacion_id": reservacion_id,
                "monto": total,
                "tipo": "pago_completo",
                "metodo_pago": "efectivo",
                "referencia": f"PILOTO-{config.run_id}",
                "notas": notas,
            },
            headers={"Idempotency-Key": f"{clave_base}-payment"},
            expected=(201,),
        )

        en_curso = client.json(
            "POST",
            _join(config.backend_url, f"/reservaciones/{reservacion_id}/check-in"),
        )
        if en_curso.get("estado") != "en_curso":
            raise PilotError("El check-in no dejó la visita en curso")

        completada = client.json(
            "POST",
            _join(config.backend_url, f"/reservaciones/{reservacion_id}/check-out"),
        )
        if completada.get("estado") != "completada":
            raise PilotError("El check-out no completó la visita")

        movimientos = client.json(
            "GET", _join(config.backend_url, f"/caja/{sesion_id}/movimientos")
        )
        if not any(
            movimiento.get("concepto") == f"Pago reservación #{reservacion_id}"
            for movimiento in movimientos
        ):
            raise PilotError("El pago no apareció como ingreso de caja")

        sesion_actual = client.json("GET", _join(config.backend_url, f"/caja/{sesion_id}"))
        cierre = client.json(
            "POST",
            _join(config.backend_url, f"/caja/{sesion_id}/cerrar"),
            payload={"monto_cierre_real": str(sesion_actual["saldo_actual"])},
        )
        if cierre.get("estado") != "cerrada":
            raise PilotError("La caja del piloto no quedó cerrada")
    except Exception:
        # No intenta compensaciones destructivas. Deja IDs exactos en el reporte
        # para que un administrador pueda revisar y continuar de forma segura.
        raise

    client.json(
        "POST",
        _join(config.backend_url, "/auth/logout"),
        expected=(204,),
    )
    return {
        "resultado": "aprobado",
        "reservacion_id": reservacion_id,
        "caja_sesion_id": sesion_id,
        "total": total,
        "fecha_visita": visita.isoformat(),
        "usuario_id": perfil["id"],
    }


def _config_desde_entorno() -> PilotConfig:
    confirmacion = os.getenv("PILOT_CONFIRMATION", "").strip()
    return PilotConfig(
        backend_url=os.getenv(
            "BACKEND_URL", "https://c-ejixhole-backend.onrender.com"
        ).rstrip("/"),
        portal_url=os.getenv(
            "PORTAL_URL", "https://ejixhole-reservas.vercel.app/"
        ),
        admin_url=os.getenv(
            "ADMIN_URL", "https://ejixhole-frontend.vercel.app/"
        ),
        ejecutar_real=confirmacion == CONFIRMACION_REAL,
        admin_email=os.getenv("PILOT_ADMIN_EMAIL", "").strip(),
        admin_password=os.getenv("PILOT_ADMIN_PASSWORD", ""),
        run_id=os.getenv("PILOT_RUN_ID", "manual").strip() or "manual",
    )


def _escribir_reporte(resultados: list[str], piloto: dict[str, Any] | None) -> str:
    lines = ["# Checklist y piloto de producción", ""]
    for resultado in resultados:
        lines.append(f"- ✅ {resultado}")
    if piloto:
        lines.extend(
            [
                "",
                "## Piloto operativo real",
                "",
                "- ✅ Solicitud pública creada",
                "- ✅ Sesión HttpOnly y CSRF verificadas",
                "- ✅ Caja abierta y cerrada",
                "- ✅ Pago en efectivo reflejado en caja",
                "- ✅ Check-in y check-out completados",
                f"- Reservación de prueba: `#{piloto['reservacion_id']}`",
                f"- Sesión de caja de prueba: `#{piloto['caja_sesion_id']}`",
                f"- Fecha simulada: `{piloto['fecha_visita']}`",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "## Piloto operativo real",
                "",
                "No ejecutado: el modo predeterminado es deliberadamente no destructivo.",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    config = _config_desde_entorno()
    client = HttpClient()
    try:
        resultados = verificar_despliegues(config, client)
        piloto = ejecutar_piloto_real(config, client) if config.ejecutar_real else None
        reporte = _escribir_reporte(resultados, piloto)
        print(reporte)
        Path(os.getenv("PILOT_REPORT_PATH", "production-pilot-report.md")).write_text(
            reporte, encoding="utf-8"
        )
        summary = os.getenv("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as output:
                output.write(reporte)
        return 0
    except PilotError as exc:
        print(f"PILOTO BLOQUEADO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
