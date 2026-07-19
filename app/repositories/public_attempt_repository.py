import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.public_anti_abuse_config import (
    PUBLIC_CLIENT_HOURLY_LIMIT,
    PUBLIC_CONTACT_DAILY_LIMIT,
    PUBLIC_IP_HOURLY_LIMIT,
)
from app.models.public_submission_attempt import PublicSubmissionAttempt


@dataclass(frozen=True)
class AttemptDecision:
    attempt: PublicSubmissionAttempt
    reason: str | None
    retry_after: int | None
    allowed: bool


class PublicAttemptRepository:
    def __init__(self, db: Session):
        self.db = db

    def _lock(self, *values: str | None) -> None:
        if self.db.get_bind().dialect.name != "postgresql":
            return
        for value in sorted({item for item in values if item}):
            number = int(value[:16], 16)
            if number >= 2**63:
                number -= 2**64
            self.db.execute(text("SELECT pg_advisory_xact_lock(:value)"), {"value": number})

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def _quota(self, field, value, now, window, limit) -> tuple[bool, int | None]:
        if value is None:
            return False, None
        rows = (
            self.db.query(PublicSubmissionAttempt)
            .filter(
                field == value,
                PublicSubmissionAttempt.created_at >= now - window,
                PublicSubmissionAttempt.allowed.is_(True),
            )
            .order_by(PublicSubmissionAttempt.created_at.asc())
            .all()
        )
        if len(rows) < limit:
            return False, None
        oldest = self._aware(rows[0].created_at)
        seconds = max(1, math.ceil((oldest + window - now).total_seconds()))
        return True, seconds

    def reserve(
        self,
        *,
        ip_hash: str,
        contact_hash: str | None,
        client_hash: str | None,
        nonce_hash: str | None,
        initial_reason: str | None,
        initial_retry_after: int | None,
        mode: str,
        now: datetime,
    ) -> AttemptDecision:
        self._lock(ip_hash, contact_hash, client_hash, nonce_hash)
        reason = initial_reason
        retry_after = initial_retry_after

        if reason is None and nonce_hash and self.db.query(PublicSubmissionAttempt).filter(
            PublicSubmissionAttempt.nonce_hash == nonce_hash
        ).first():
            reason = "challenge_reused"

        checks = (
            (PublicSubmissionAttempt.ip_hash, ip_hash, timedelta(hours=1), PUBLIC_IP_HOURLY_LIMIT, "ip_limit"),
            (PublicSubmissionAttempt.contact_hash, contact_hash, timedelta(days=1), PUBLIC_CONTACT_DAILY_LIMIT, "contact_limit"),
            (PublicSubmissionAttempt.client_hash, client_hash, timedelta(hours=1), PUBLIC_CLIENT_HOURLY_LIMIT, "client_limit"),
        )
        for field, value, window, limit, label in checks:
            if reason is not None:
                break
            exceeded, seconds = self._quota(field, value, now, window, limit)
            if exceeded:
                reason, retry_after = label, seconds

        allowed = reason is None or mode == "monitor"
        stored_nonce = None if reason == "challenge_reused" else nonce_hash
        attempt = PublicSubmissionAttempt(
            ip_hash=ip_hash,
            contact_hash=contact_hash,
            client_hash=client_hash,
            nonce_hash=stored_nonce,
            allowed=allowed,
            mode=mode,
            reason=reason or "ok",
        )
        self.db.add(attempt)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            reason = "challenge_reused"
            allowed = mode == "monitor"
            attempt = PublicSubmissionAttempt(
                ip_hash=ip_hash,
                contact_hash=contact_hash,
                client_hash=client_hash,
                nonce_hash=None,
                allowed=allowed,
                mode=mode,
                reason=reason,
            )
            self.db.add(attempt)
            self.db.commit()
        return AttemptDecision(attempt, reason, retry_after, allowed)

    def release(self, attempt: PublicSubmissionAttempt) -> None:
        if not attempt.allowed:
            return
        self.db.query(PublicSubmissionAttempt).filter(PublicSubmissionAttempt.id == attempt.id).delete()
        self.db.commit()
