"""The two data shapes that flow through the pipeline.

`RawRecord` is what every feeder emits; nothing downstream knows how it was
obtained.  `NormalizedEvent` is what every adapter emits and what the repository
writes -- it mirrors the `events` table.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

RecordFormat = Literal["ics", "json", "html", "xml"]
EventStatus = Literal["active", "cancelled", "removed"]


class RawRecord(BaseModel):
    """One unit of fetched content: a whole ICS document, a JSON page, an HTML listing."""

    model_config = ConfigDict(frozen=True)

    format: RecordFormat
    url: str
    payload: Any
    fetched_at: dt.datetime = Field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    meta: dict[str, Any] = Field(default_factory=dict)


class FeedContext(BaseModel):
    """Everything an adapter needs that does not come from the payload itself.

    Built once per run from the feeder spec joined to its `calendars` registry row.
    """

    model_config = ConfigDict(frozen=True)

    feeder_id: str
    source: str
    host: str | None = None
    source_calendar_name: str | None = None
    calendar_id: UUID | None = None
    calendar_url: str | None = None
    timezone: str = "America/New_York"
    static_tags: tuple[str, ...] = ()
    registry_tags: tuple[str, ...] = ()
    horizon_days: int = 180
    base_url: str | None = None


class NormalizedEvent(BaseModel):
    """One event, in the shape the `events` table stores.

    Adapters populate the descriptive fields; `normalize.pipeline` fills in the
    derived ones (`is_virtual`, `meeting_link`, `tags`, `dedupe_key`, `content_hash`).
    """

    event_name: str
    host: str | None = None
    source: str
    source_calendar_name: str | None = None
    calendar_id: UUID | None = None

    starts_at: dt.datetime
    ends_at: dt.datetime | None = None
    all_day: bool = False

    location: str | None = None
    is_virtual: bool = False
    event_url: str | None = None
    meeting_link: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)

    source_uid: str | None = None
    dedupe_key: str = ""
    content_hash: str = ""
    status: EventStatus = "active"
    raw: dict[str, Any] = Field(default_factory=dict)


class UpsertStats(BaseModel):
    """What one `upsert_many` call did."""

    inserted: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.inserted + self.updated + self.unchanged

    def __str__(self) -> str:
        return f"{self.inserted} new, {self.updated} changed, {self.unchanged} unchanged"


class RunReport(BaseModel):
    """Outcome of running one feeder end to end."""

    feeder_id: str
    ok: bool
    records: int = 0
    events: int = 0
    stats: UpsertStats = Field(default_factory=UpsertStats)
    removed: int = 0
    duration_seconds: float = 0.0
    error: str | None = None
