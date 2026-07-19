from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.public_anti_abuse_config import (
    PUBLIC_ANTI_ABUSE_MODE,
    PUBLIC_CHALLENGE_MIN_SECONDS,
    PUBLIC_CHALLENGE_TTL_SECONDS,
    PUBLIC_CLIENT_HOURLY_LIMIT,
    PUBLIC_CONTACT_DAILY_LIMIT,
    PUBLIC_IP_HOURLY_LIMIT,
)
from app.models.public_submission_attempt import PublicSubmissionAttempt
from app.services.audit_service import AuditService


class PublicFormGuardService:
    def __init__(self, db: Session):
        self.db = db
        self._key = settings.JWT_SECRET_KEY.encode("utf-8")

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def _signature(self, payload: str) -> str:
        digest = hmac.new(
            self._key,
            f"public-form-v1:{payload}".encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return self._b64(digest)

    def _pseudonym(self, namespace: str, value: str | None) -> str | None:
        if not value:
            return None
        return hmac.new(
            self._key,
            f"{namespace}:{value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _client_ip(request: Request) -> str:
        forwarded = [item.strip() for item in request.headers.get("x-forwarded-for", "").split(",") if item.strip()]
        if forwarded:
            return forwarded[-1]
        return request.client.host if request.client else "unknown"

    def create_challenge(self) -> dict:
        now = int(time.time())
        payload = {
            "v": 1,
            "iat": now,
            "exp": now + PUBLIC_CHALLENGE_TTL_SECONDS,
            "nonce": secrets.token_urlsafe(18),
        }
        encoded = self._b64(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        value = f"{encoded}.{self._signature(encoded)}"
        return {
            "token": value,
            "issued_at": datetime.fromtimestamp(payload["iat"], timezone.utc),
            "expires_at": datetime.fromtimestamp(payload["exp"], timezone.utc),
            "minimum_wait_seconds": PUBLIC_CHALLENGE_MIN_SECONDS,
            "enforcement_mode": PUBLIC_ANTI_ABUSE_MODE,
        }

    def _check_challenge(self, value: str | None) -> tuple[str | None, str | None]:
        if not value:
            return "challenge_missing", None
        try:
            encoded, signature = value.split(".", 1)
            if not hmac.compare_digest(signature, self._signature(encoded)):
                return "challenge_invalid", None
            payload = json.loads(self._unb64(encoded))
            now = int(time.time())
            if payload.get("v") != 1 or not isinstance(payload.get("nonce"), str):
                return "challenge_invalid", None
            issued_at = int(payload["iat"])
            expires_at = int(payload["exp"])
            if issued_at > now + 60:
                return "challenge_invalid", None
            if now < issued_at + PUBLIC_CHALLENGE_MIN_SECONDS:
                return "challenge_too_fast", payload["nonce"]
            if now > expires_at:
                return "challenge_expired", payload["nonce"]
            return None, payload["nonce"]
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return "challenge_invalid", None

    def _count(self, field, value: str | None, since: datetime) -> int:
        if value is None:
            return 0
        return (
            self.db.query(PublicSubmissionAttempt)
            .filter(
                field == value,
                PublicSubmissionAttempt.created_at >= since,
                PublicSubmissionAttempt.allowed.is_(True),
            )
            .count()
        )

    def validate_and_record(self, request: Request, data) -> None:
        now = datetime.now(timezone.utc)
        ip_hash = self._pseudonym("ip", self._client_ip(request))
        email = str(getattr(data, "email", "")).strip().lower()
        phone = "".join(char for char in str(getattr(data, "telefono", "")) if char.isdigit())
        contact_hash = self._pseudonym("contact", f"{email}|{phone}")
        client_value = request.headers.get("x-public-client", "").strip()[:120]
        client_hash = self._pseudonym("client", client_value)
        reason, nonce = self._check_challenge(getattr(data, "form_challenge", None))

        if str(getattr(data, "website", "") or "").strip():
            reason = "honeypot_filled"
        elif reason is None and self._count(
            PublicSubmissionAttempt.ip_hash, ip_hash, now - timedelta(hours=1)
        ) >= PUBLIC_IP_HOURLY_LIMIT:
            reason = "ip_limit"
        elif reason is None and self._count(
            PublicSubmissionAttempt.contact_hash, contact_hash, now - timedelta(days=1)
        ) >= PUBLIC_CONTACT_DAILY_LIMIT:
            reason = "contact_limit"
        elif reason is None and client_hash and self._count(
            PublicSubmissionAttempt.client_hash, client_hash, now - timedelta(hours=1)
        ) >= PUBLIC_CLIENT_HOURLY_LIMIT:
            reason = "client_limit"

        violation = reason is not None
        allowed = not violation or PUBLIC_ANTI_ABUSE_MODE == "monitor"
        attempt = PublicSubmissionAttempt(
            ip_hash=ip_hash,
            contact_hash=contact_hash,
            client_hash=client_hash,
            nonce_hash=self._pseudonym("nonce", nonce),
            allowed=allowed,
            mode=PUBLIC_ANTI_ABUSE_MODE,
            reason=reason or "ok",
        )
        self.db.add(attempt)
        self.db.commit()

        if violation:
            AuditService(self.db).registrar(
                actor=None,
                accion="publico.antiabuso_detectado",
                entidad_tipo="public_submission",
                entidad_id=attempt.id,
                request=request,
                contexto={"reason": reason, "mode": PUBLIC_ANTI_ABUSE_MODE},
                origen="portal_publico",
            )

        if not allowed:
            if reason in {"ip_limit", "contact_limit", "client_limit", "challenge_too_fast"}:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="No fue posible procesar la solicitud en este momento.",
                    headers={"Retry-After": "60"},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible validar el formulario.",
            )
