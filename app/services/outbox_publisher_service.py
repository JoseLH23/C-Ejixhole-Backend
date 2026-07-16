"""Publicador confiable de eventos del outbox hacia MH-Core."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import os
import socket
import time
from typing import Callable
from urllib.parse import urlparse
from uuid import uuid4

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import SessionLocal
from app.models.outbox_event import OutboxEvent


logger = logging.getLogger("ejixhole.outbox")
EVENT_CONTRACT_VERSION = "v1"
MAX_DIAGNOSTIC_CHARS = 2000
RETRYABLE_HTTP_STATUSES = {408, 425, 429}


class OutboxPublisherConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OutboxPublisherConfig:
    events_url: str
    signing_secret: str
    batch_size: int = 10
    max_attempts: int = 8
    lease_seconds: int = 120
    initial_backoff_seconds: int = 10
    max_backoff_seconds: int = 3600
    request_timeout_seconds: float = 10.0
    poll_interval_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "OutboxPublisherConfig":
        def integer(name: str, default: int) -> int:
            raw = os.getenv(name, str(default))
            try:
                return int(raw)
            except ValueError as exc:
                raise OutboxPublisherConfigurationError(
                    f"{name} debe ser entero."
                ) from exc

        def decimal(name: str, default: float) -> float:
            raw = os.getenv(name, str(default))
            try:
                return float(raw)
            except ValueError as exc:
                raise OutboxPublisherConfigurationError(
                    f"{name} debe ser numérico."
                ) from exc

        config = cls(
            events_url=os.getenv("MH_CORE_EVENTS_URL", "").strip(),
            signing_secret=os.getenv("MH_CORE_EVENT_SIGNING_SECRET", "").strip(),
            batch_size=integer("OUTBOX_BATCH_SIZE", 10),
            max_attempts=integer("OUTBOX_MAX_ATTEMPTS", 8),
            lease_seconds=integer("OUTBOX_LEASE_SECONDS", 120),
            initial_backoff_seconds=integer("OUTBOX_INITIAL_BACKOFF_SECONDS", 10),
            max_backoff_seconds=integer("OUTBOX_MAX_BACKOFF_SECONDS", 3600),
            request_timeout_seconds=decimal("OUTBOX_REQUEST_TIMEOUT_SECONDS", 10),
            poll_interval_seconds=decimal("OUTBOX_POLL_INTERVAL_SECONDS", 10),
        )
        config.validate()
        return config

    def validate(self) -> None:
        parsed = urlparse(self.events_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise OutboxPublisherConfigurationError(
                "MH_CORE_EVENTS_URL no es una URL HTTP válida."
            )
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise OutboxPublisherConfigurationError(
                "MH_CORE_EVENTS_URL no debe contener credenciales, query ni fragmento."
            )
        if settings.ENVIRONMENT == "production" and parsed.scheme != "https":
            raise OutboxPublisherConfigurationError(
                "MH_CORE_EVENTS_URL debe usar HTTPS en producción."
            )
        if len(self.signing_secret) < 32:
            raise OutboxPublisherConfigurationError(
                "MH_CORE_EVENT_SIGNING_SECRET no está configurada o es demasiado corta."
            )
        if not 1 <= self.batch_size <= 100:
            raise OutboxPublisherConfigurationError(
                "OUTBOX_BATCH_SIZE debe estar entre 1 y 100."
            )
        if not 1 <= self.max_attempts <= 50:
            raise OutboxPublisherConfigurationError(
                "OUTBOX_MAX_ATTEMPTS debe estar entre 1 y 50."
            )
        if not 5 <= self.request_timeout_seconds <= 60:
            raise OutboxPublisherConfigurationError(
                "OUTBOX_REQUEST_TIMEOUT_SECONDS debe estar entre 5 y 60."
            )
        if self.lease_seconds < self.request_timeout_seconds * 3:
            raise OutboxPublisherConfigurationError(
                "OUTBOX_LEASE_SECONDS debe ser al menos tres veces el timeout HTTP."
            )
        if self.initial_backoff_seconds < 1:
            raise OutboxPublisherConfigurationError(
                "OUTBOX_INITIAL_BACKOFF_SECONDS debe ser positivo."
            )
        if self.max_backoff_seconds < self.initial_backoff_seconds:
            raise OutboxPublisherConfigurationError(
                "OUTBOX_MAX_BACKOFF_SECONDS no puede ser menor al inicial."
            )
        if not 1 <= self.poll_interval_seconds <= 300:
            raise OutboxPublisherConfigurationError(
                "OUTBOX_POLL_INTERVAL_SECONDS debe estar entre 1 y 300."
            )


@dataclass(frozen=True)
class OutboxEventSnapshot:
    id: str
    event_key: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    schema_version: int
    payload: dict
    occurred_at: datetime


@dataclass(frozen=True)
class PublishStats:
    claimed: int = 0
    published: int = 0
    retried: int = 0
    dead_letter: int = 0
    skipped: int = 0


class OutboxPublisher:
    def __init__(
        self,
        config: OutboxPublisherConfig | None = None,
        *,
        session_factory: Callable[[], Session] = SessionLocal,
        http_session: requests.Session | None = None,
        worker_id: str | None = None,
        now: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or OutboxPublisherConfig.from_env()
        self.config.validate()
        self.session_factory = session_factory
        self.http_session = http_session or requests.Session()
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        )
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.sleeper = sleeper

    @staticmethod
    def _utc_iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _diagnostic(value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()[:MAX_DIAGNOSTIC_CHARS]

    def _backoff_seconds(self, attempts: int) -> int:
        delay = self.config.initial_backoff_seconds * (2 ** max(attempts - 1, 0))
        return min(delay, self.config.max_backoff_seconds)

    def claim_batch(self) -> list[str]:
        db = self.session_factory()
        now = self.now()
        cutoff = now - timedelta(seconds=self.config.lease_seconds)
        claimed_ids: list[str] = []
        try:
            stale_events = (
                db.query(OutboxEvent)
                .filter(
                    OutboxEvent.status == "processing",
                    OutboxEvent.locked_at.is_not(None),
                    OutboxEvent.locked_at < cutoff,
                )
                .order_by(OutboxEvent.locked_at.asc())
                .with_for_update(skip_locked=True)
                .limit(self.config.batch_size)
                .all()
            )
            for event in stale_events:
                event.attempts += 1
                event.locked_at = None
                event.locked_by = None
                event.last_error = "Lease de publicación vencido; el evento será reintentado."
                if event.attempts >= self.config.max_attempts:
                    event.status = "dead_letter"
                    event.dead_lettered_at = now
                else:
                    event.status = "failed"
                    event.available_at = now

            db.flush()
            candidates = (
                db.query(OutboxEvent)
                .filter(
                    OutboxEvent.status.in_(("pending", "failed")),
                    OutboxEvent.available_at <= now,
                    OutboxEvent.attempts < self.config.max_attempts,
                )
                .order_by(OutboxEvent.available_at.asc(), OutboxEvent.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(self.config.batch_size)
                .all()
            )
            for event in candidates:
                event.status = "processing"
                event.locked_at = now
                event.locked_by = self.worker_id
                claimed_ids.append(event.id)

            db.commit()
            return claimed_ids
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _load_owned_snapshot(self, event_id: str) -> OutboxEventSnapshot | None:
        db = self.session_factory()
        try:
            event = (
                db.query(OutboxEvent)
                .filter(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == "processing",
                    OutboxEvent.locked_by == self.worker_id,
                )
                .with_for_update()
                .first()
            )
            if event is None:
                db.rollback()
                return None
            event.locked_at = self.now()
            snapshot = OutboxEventSnapshot(
                id=event.id,
                event_key=event.event_key,
                event_type=event.event_type,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                schema_version=event.schema_version,
                payload=dict(event.payload),
                occurred_at=event.occurred_at,
            )
            db.commit()
            return snapshot
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _body(self, event: OutboxEventSnapshot) -> bytes:
        envelope = {
            "event_id": event.id,
            "event_key": event.event_key,
            "event_type": event.event_type,
            "schema_version": event.schema_version,
            "source": "ejixhole",
            "occurred_at": self._utc_iso(event.occurred_at),
            "aggregate": {
                "type": event.aggregate_type,
                "id": event.aggregate_id,
            },
            "payload": event.payload,
        }
        return json.dumps(
            envelope,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")

    def _signed_headers(self, event_id: str, body: bytes) -> dict[str, str]:
        timestamp = str(int(self.now().timestamp()))
        signed_content = timestamp.encode("ascii") + b"." + body
        signature = hmac.new(
            self.config.signing_secret.encode("utf-8"),
            signed_content,
            hashlib.sha256,
        ).hexdigest()
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "EjiXhole-Outbox-Publisher/1.0",
            "X-MH-Event-Id": event_id,
            "X-MH-Event-Timestamp": timestamp,
            "X-MH-Event-Signature": f"sha256={signature}",
        }

    def _mark_success(self, event_id: str, response: requests.Response) -> bool:
        db = self.session_factory()
        try:
            event = (
                db.query(OutboxEvent)
                .filter(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == "processing",
                    OutboxEvent.locked_by == self.worker_id,
                )
                .with_for_update()
                .first()
            )
            if event is None:
                db.rollback()
                return False
            event.attempts += 1
            event.status = "published"
            event.published_at = self.now()
            event.locked_at = None
            event.locked_by = None
            event.last_http_status = response.status_code
            event.last_error = None
            event.last_response = self._diagnostic(response.text)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _mark_failure(
        self,
        event_id: str,
        *,
        error: str,
        permanent: bool,
        http_status: int | None = None,
        response_text: str | None = None,
    ) -> str:
        db = self.session_factory()
        try:
            event = (
                db.query(OutboxEvent)
                .filter(
                    OutboxEvent.id == event_id,
                    OutboxEvent.status == "processing",
                    OutboxEvent.locked_by == self.worker_id,
                )
                .with_for_update()
                .first()
            )
            if event is None:
                db.rollback()
                return "skipped"

            event.attempts += 1
            event.locked_at = None
            event.locked_by = None
            event.last_http_status = http_status
            event.last_error = self._diagnostic(error)
            event.last_response = self._diagnostic(response_text)

            if permanent or event.attempts >= self.config.max_attempts:
                event.status = "dead_letter"
                event.dead_lettered_at = self.now()
                result = "dead_letter"
            else:
                event.status = "failed"
                event.available_at = self.now() + timedelta(
                    seconds=self._backoff_seconds(event.attempts)
                )
                result = "retried"

            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _valid_receipt(response: requests.Response, event_id: str) -> tuple[bool, str]:
        if response.headers.get("X-MH-Event-Contract") != EVENT_CONTRACT_VERSION:
            return False, "MH-Core no confirmó el contrato de eventos v1."
        try:
            payload = response.json()
        except ValueError:
            return False, "MH-Core devolvió una respuesta JSON inválida."
        if payload.get("accepted") is not True or str(payload.get("event_id")) != event_id:
            return False, "MH-Core no confirmó la identidad del evento aceptado."
        return True, ""

    def publish_event(self, event_id: str) -> str:
        event = self._load_owned_snapshot(event_id)
        if event is None:
            return "skipped"

        body = self._body(event)
        headers = self._signed_headers(event.id, body)
        try:
            response = self.http_session.post(
                self.config.events_url,
                data=body,
                headers=headers,
                timeout=self.config.request_timeout_seconds,
            )
        except requests.RequestException as exc:
            logger.warning(
                "Fallo de red al publicar event_id=%s type=%s error=%s",
                event.id,
                event.event_type,
                type(exc).__name__,
            )
            return self._mark_failure(
                event.id,
                error=f"Error de red: {type(exc).__name__}",
                permanent=False,
            )

        if 200 <= response.status_code < 300:
            valid, validation_error = self._valid_receipt(response, event.id)
            if valid:
                return "published" if self._mark_success(event.id, response) else "skipped"
            return self._mark_failure(
                event.id,
                error=validation_error,
                permanent=False,
                http_status=response.status_code,
                response_text=response.text,
            )

        retryable = (
            response.status_code in RETRYABLE_HTTP_STATUSES
            or response.status_code >= 500
        )
        return self._mark_failure(
            event.id,
            error=f"MH-Core devolvió HTTP {response.status_code}.",
            permanent=not retryable,
            http_status=response.status_code,
            response_text=response.text,
        )

    def publish_once(self) -> PublishStats:
        event_ids = self.claim_batch()
        counts = {
            "published": 0,
            "retried": 0,
            "dead_letter": 0,
            "skipped": 0,
        }
        for event_id in event_ids:
            result = self.publish_event(event_id)
            counts[result] += 1

        stats = PublishStats(claimed=len(event_ids), **counts)
        if stats.claimed:
            logger.info(
                "Ciclo outbox worker=%s claimed=%s published=%s retried=%s dead_letter=%s skipped=%s",
                self.worker_id,
                stats.claimed,
                stats.published,
                stats.retried,
                stats.dead_letter,
                stats.skipped,
            )
        return stats

    def run_forever(self) -> None:
        logger.info("Publicador outbox iniciado worker=%s", self.worker_id)
        while True:
            try:
                self.publish_once()
            except Exception:
                logger.exception("Error inesperado en el ciclo del publicador outbox.")
            self.sleeper(self.config.poll_interval_seconds)
