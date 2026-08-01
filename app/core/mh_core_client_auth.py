"""Credenciales salientes para llamadas EjiXhole Backend -> MH-Core."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class MhCoreClientCredential:
    api_key: str
    service_id: str | None
    legacy: bool = False


def obtener_credencial_mh_core() -> MhCoreClientCredential | None:
    """Prefiere identidad dedicada y conserva transición de la clave antigua.

    `MH_CORE_SERVICE_KEY` no participa aquí: esa clave autentica solicitudes en
    sentido contrario (MH-Core -> EjiXhole Backend).
    """
    dedicated = os.getenv("MH_CORE_EJIXHOLE_KEY", "").strip()
    if dedicated:
        return MhCoreClientCredential(
            api_key=dedicated,
            service_id="ejixhole-backend",
        )

    legacy = os.getenv("MH_CORE_API_KEY", "").strip()
    if legacy:
        return MhCoreClientCredential(
            api_key=legacy,
            service_id=None,
            legacy=True,
        )
    return None


def cabeceras_mh_core(credential: MhCoreClientCredential) -> dict[str, str]:
    headers = {
        "X-API-Key": credential.api_key,
        "Accept": "application/json",
    }
    if credential.service_id:
        headers["X-Service-ID"] = credential.service_id
    return headers
