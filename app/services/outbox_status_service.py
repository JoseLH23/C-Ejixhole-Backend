"""Diagnóstico administrativo del publicador de eventos hacia MH-Core."""
from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.outbox_event import OUTBOX_STATUSES, OutboxEvent
from app.schemas.outbox_status import OutboxChannelStatusOut, OutboxEventStatusOut
from app.services.outbox_publisher_service import OutboxPublisherConfig, OutboxPublisherConfigurationError


class OutboxStatusService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _serialize(event: OutboxEvent | None) -> OutboxEventStatusOut | None:
        if event is None:
            return None
        return OutboxEventStatusOut(
            event_id=UUID(event.id),
            event_key=event.event_key,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            schema_version=event.schema_version,
            status=event.status,
            attempts=event.attempts,
            available_at=event.available_at,
            occurred_at=event.occurred_at,
            published_at=event.published_at,
            dead_lettered_at=event.dead_lettered_at,
            locked_at=event.locked_at,
            last_http_status=event.last_http_status,
        )

    @staticmethod
    def _url_is_valid(events_url: str) -> bool:
        try:
            OutboxPublisherConfig(events_url=events_url, signing_secret="x" * 48).validate()
        except OutboxPublisherConfigurationError:
            return False
        return True

    @staticmethod
    def _configuration_is_valid(events_url: str, signing_secret: str) -> bool:
        try:
            OutboxPublisherConfig(
                events_url=events_url,
                signing_secret=signing_secret,
            ).validate()
        except OutboxPublisherConfigurationError:
            return False
        return True

    def status(self) -> OutboxChannelStatusOut:
        rows = (
            self.db.query(OutboxEvent.status, func.count(OutboxEvent.id))
            .group_by(OutboxEvent.status)
            .all()
        )
        counts = {status: 0 for status in OUTBOX_STATUSES}
        counts.update({status: int(total) for status, total in rows})

        latest = (
            self.db.query(OutboxEvent)
            .order_by(OutboxEvent.created_at.desc(), OutboxEvent.id.desc())
            .first()
        )
        latest_published = (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.status == "published")
            .order_by(OutboxEvent.published_at.desc(), OutboxEvent.id.desc())
            .first()
        )

        events_url = os.getenv("MH_CORE_EVENTS_URL", "").strip()
        signing_secret = os.getenv("MH_CORE_EVENT_SIGNING_SECRET", "").strip()
        return OutboxChannelStatusOut(
            configured=self._configuration_is_valid(events_url, signing_secret),
            events_url_configured=self._url_is_valid(events_url),
            signing_secret_configured=len(signing_secret) >= 32,
            total_events=sum(counts.values()),
            by_status=counts,
            pending_delivery=counts["pending"] + counts["processing"] + counts["failed"],
            dead_letter=counts["dead_letter"],
            latest_event=self._serialize(latest),
            latest_published=self._serialize(latest_published),
        )

    def event(self, event_id: UUID) -> OutboxEventStatusOut | None:
        event = (
            self.db.query(OutboxEvent)
            .filter(OutboxEvent.id == str(event_id))
            .first()
        )
        return self._serialize(event)
