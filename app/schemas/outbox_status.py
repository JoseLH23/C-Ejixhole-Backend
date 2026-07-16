"""Respuestas administrativas del canal de eventos hacia MH-Core."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OutboxEventStatusOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_key: str
    event_type: str
    aggregate_type: Literal["reservation", "payment"]
    aggregate_id: str
    schema_version: int
    status: Literal["pending", "processing", "published", "failed", "dead_letter"]
    attempts: int
    available_at: datetime
    occurred_at: datetime
    published_at: datetime | None
    dead_lettered_at: datetime | None
    locked_at: datetime | None
    last_http_status: int | None


class OutboxChannelStatusOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    events_url_configured: bool
    signing_secret_configured: bool
    worker_process_required: Literal[True] = True
    total_events: int
    by_status: dict[str, int]
    pending_delivery: int
    dead_letter: int
    latest_event: OutboxEventStatusOut | None
    latest_published: OutboxEventStatusOut | None
