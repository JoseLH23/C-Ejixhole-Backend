import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings
from app.core.public_anti_abuse_config import PUBLIC_CHALLENGE_MIN_SECONDS, PUBLIC_CHALLENGE_TTL_SECONDS


@dataclass(frozen=True)
class ChallengeCheck:
    reason: str | None
    nonce: str | None
    retry_after: int | None = None


class FormChallenge:
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

    def create(self, mode: str) -> dict:
        now = int(time.time())
        payload = {
            "v": 1,
            "iat": now,
            "exp": now + PUBLIC_CHALLENGE_TTL_SECONDS,
            "nonce": secrets.token_urlsafe(18),
        }
        encoded = self._encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        return {
            "token": f"{encoded}.{self._signature(encoded)}",
            "issued_at": datetime.fromtimestamp(payload["iat"], timezone.utc),
            "expires_at": datetime.fromtimestamp(payload["exp"], timezone.utc),
            "minimum_wait_seconds": PUBLIC_CHALLENGE_MIN_SECONDS,
            "enforcement_mode": mode,
        }

    def check(self, value: str | None) -> ChallengeCheck:
        if not value:
            return ChallengeCheck("challenge_missing", None)
        try:
            encoded, signature = value.split(".", 1)
            if not hmac.compare_digest(signature, self._signature(encoded)):
                return ChallengeCheck("challenge_invalid", None)
            payload = json.loads(self._decode(encoded))
            now = int(time.time())
            if payload.get("v") != 1 or not isinstance(payload.get("nonce"), str):
                return ChallengeCheck("challenge_invalid", None)
            issued_at = int(payload["iat"])
            expires_at = int(payload["exp"])
            if issued_at > now + 60:
                return ChallengeCheck("challenge_invalid", None)
            ready_at = issued_at + PUBLIC_CHALLENGE_MIN_SECONDS
            if now < ready_at:
                return ChallengeCheck("challenge_too_fast", payload["nonce"], max(1, ready_at - now))
            if now > expires_at:
                return ChallengeCheck("challenge_expired", payload["nonce"])
            return ChallengeCheck(None, payload["nonce"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return ChallengeCheck("challenge_invalid", None)
