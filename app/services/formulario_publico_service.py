import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.form_challenge import FormChallenge
from app.core.public_anti_abuse_config import PUBLIC_ANTI_ABUSE_MODE
from app.models.public_submission_attempt import PublicSubmissionAttempt
from app.repositories.public_attempt_repository import PublicAttemptRepository
from app.services.audit_service import AuditService


class FormularioPublicoService:
    def __init__(self, db: Session):
        self.db = db
        self.challenge = FormChallenge()
        self.attempts = PublicAttemptRepository(db)

    @staticmethod
    def _client_ip(request: Request) -> str:
        values = [item.strip() for item in request.headers.get("x-forwarded-for", "").split(",") if item.strip()]
        if values:
            return values[-1]
        return request.client.host if request.client else "unknown"

    @staticmethod
    def _pseudonym(namespace: str, value: str | None) -> str | None:
        if not value:
            return None
        return hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            f"{namespace}:{value}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def create_challenge(self) -> dict:
        return self.challenge.create(PUBLIC_ANTI_ABUSE_MODE)

    def validate_and_reserve(self, request: Request, data) -> PublicSubmissionAttempt:
        email = str(getattr(data, "email", "")).strip().lower()
        phone = "".join(char for char in str(getattr(data, "telefono", "")) if char.isdigit())
        client_value = request.headers.get("x-public-client", "").strip()[:120]
        check = self.challenge.check(getattr(data, "form_challenge", None))
        reason = check.reason
        if str(getattr(data, "website", "") or "").strip():
            reason = "honeypot_filled"

        decision = self.attempts.reserve(
            ip_hash=self._pseudonym("ip", self._client_ip(request)),
            contact_hash=self._pseudonym("contact", f"{email}|{phone}"),
            client_hash=self._pseudonym("client", client_value),
            nonce_hash=self._pseudonym("nonce", check.nonce),
            initial_reason=reason,
            initial_retry_after=check.retry_after,
            mode=PUBLIC_ANTI_ABUSE_MODE,
            now=datetime.now(timezone.utc),
        )

        if decision.reason:
            AuditService(self.db).registrar(
                actor=None,
                accion="publico.antiabuso_detectado",
                entidad_tipo="public_submission",
                entidad_id=decision.attempt.id,
                request=request,
                contexto={"reason": decision.reason, "mode": PUBLIC_ANTI_ABUSE_MODE},
                origen="portal_publico",
            )

        if not decision.allowed:
            if decision.retry_after is not None:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="No fue posible procesar la solicitud en este momento.",
                    headers={"Retry-After": str(decision.retry_after)},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fue posible validar el formulario.",
            )
        return decision.attempt

    def release(self, attempt: PublicSubmissionAttempt) -> None:
        self.attempts.release(attempt)
