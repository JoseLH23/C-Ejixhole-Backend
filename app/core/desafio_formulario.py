import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.core.proteccion_publica_config import ESPERA_MINIMA_SEGUNDOS, VIGENCIA_DESAFIO_SEGUNDOS


@dataclass(frozen=True)
class ResultadoDesafio:
    motivo: str | None
    nonce: str | None
    reintentar_en: int | None = None


class DesafioFormulario:
    def __init__(self):
        self._key = settings.JWT_SECRET_KEY.encode("utf-8")

    @staticmethod
    def _encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _signature(self, payload: str) -> str:
        digest = hmac.new(
            self._key,
            f"public-form-v1:{payload}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return self._encode(digest)

    def crear(self, modo: str) -> dict:
        ahora = int(time.time())
        payload = {
            "v": 1,
            "iat": ahora,
            "exp": ahora + VIGENCIA_DESAFIO_SEGUNDOS,
            "nonce": secrets.token_urlsafe(18),
        }
        encoded = self._encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        return {
            "token": f"{encoded}.{self._signature(encoded)}",
            "issued_at": datetime.fromtimestamp(payload["iat"], timezone.utc),
            "expires_at": datetime.fromtimestamp(payload["exp"], timezone.utc),
            "minimum_wait_seconds": ESPERA_MINIMA_SEGUNDOS,
            "enforcement_mode": modo,
        }

    def validar(self, value: str | None) -> ResultadoDesafio:
        if not value:
            return ResultadoDesafio("challenge_missing", None)
        try:
            encoded, signature = value.split(".", 1)
            if not hmac.compare_digest(signature, self._signature(encoded)):
                return ResultadoDesafio("challenge_invalid", None)
            payload = json.loads(self._decode(encoded))
            ahora = int(time.time())
            if payload.get("v") != 1 or not isinstance(payload.get("nonce"), str):
                return ResultadoDesafio("challenge_invalid", None)
            emitido = int(payload["iat"])
            expira = int(payload["exp"])
            if emitido > ahora + 60:
                return ResultadoDesafio("challenge_invalid", None)
            listo = emitido + ESPERA_MINIMA_SEGUNDOS
            if ahora < listo:
                return ResultadoDesafio("challenge_too_fast", payload["nonce"], max(1, listo - ahora))
            if ahora > expira:
                return ResultadoDesafio("challenge_expired", payload["nonce"])
            return ResultadoDesafio(None, payload["nonce"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return ResultadoDesafio("challenge_invalid", None)
