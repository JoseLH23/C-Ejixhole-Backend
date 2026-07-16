"""Autenticación de servicio para integraciones internas de solo lectura."""
from __future__ import annotations

import hmac
import os
from dataclasses import dataclass

from fastapi import Header, HTTPException, status

MH_CORE_SCOPE = "ejixhole:read:operations"


@dataclass(frozen=True)
class ServicePrincipal:
    name: str
    scopes: frozenset[str]


def require_mh_core_readonly(
    x_mh_service_key: str | None = Header(default=None, alias="X-MH-Service-Key"),
) -> ServicePrincipal:
    """Valida la credencial exclusiva de MH-Core y falla cerrado.

    La clave se lee en cada solicitud para facilitar rotación sin acoplarla al
    JWT administrativo. Esta identidad solo concede el alcance fijo de lectura
    operativa; no representa a un usuario ni habilita rutas de escritura.
    """
    clave_real = os.getenv("MH_CORE_SERVICE_KEY", "").strip()

    if not clave_real:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La integración con MH-Core no está configurada.",
        )
    if len(clave_real) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La credencial de integración con MH-Core no cumple la longitud mínima.",
        )
    if not x_mh_service_key or not hmac.compare_digest(x_mh_service_key, clave_real):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credencial de servicio inválida o faltante.",
        )

    return ServicePrincipal(name="mh-core", scopes=frozenset({MH_CORE_SCOPE}))
