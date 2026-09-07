"""SQLAlchemy models for the two tables.

`calendars` mirrors penn-calendars.csv verbatim (the source registry).
`events` is the unified event store the frontend will read.

Note the GENERATED columns on `events`: `event_date`, `start_time` and `end_time`
are derived by Postgres from the canonical `starts_at`/`ends_at` timestamps, so the
literal date/time fields can never drift out of sync with the values the indexes
sort on.  `timestamptz AT TIME ZONE '<literal zone>'` is IMMUTABLE, which is what
makes it legal in a generated column.
"""
from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

DISPLAY_TZ = "America/New_York"


class Base(DeclarativeBase):
    pass


def _local(column: str, cast: str) -> str:
    """SQL for rendering a timestamptz column in Penn's local timezone."""
    return f"(({column} AT TIME ZONE '{DISPLAY_TZ}')::{cast})"


class Calendar(Base):
    """Table 1 -- the source registry, one row per line of penn-calendars.csv."""

    __tablename__ = "calendars"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # The eleven CSV columns, snake_cased and otherwise untouched.
    unit: Mapped[str | None] = mapped_column(Text)
    school_division: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    calendar_name: Mapped[str | None] = mapped_column(Text)
    calendar_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    platform_cms: Mapped[str | None] = mapped_column(Text)
    how_content_is_rendered: Mapped[str | None] = mapped_column(Text)
    feed_api_endpoint: Mapped[str | None] = mapped_column(Text)
    best_fetch_method: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    imported_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["Event"]] = relationship(back_populates="calendar")

    __table_args__ = (
        Index("ix_calendars_school_division", "school_division"),
        Index("ix_calendars_platform_cms", "platform_cms"),
    )

    def __repr__(self) -> str:
        return f"<Calendar {self.calendar_name!r} {self.calendar_url}>"


class Event(Base):
    """Table 2 -- the unified event store."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    host: Mapped[str | None] = mapped_column(Text)  # owning school / department
    source: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. ics:events.med.upenn.edu
    source_calendar_name: Mapped[str | None] = mapped_column(Text)
    calendar_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("calendars.id", ondelete="SET NULL")
    )

    starts_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    event_date: Mapped[dt.date] = mapped_column(
        Date, Computed(_local("starts_at", "date"), persisted=True)
    )
    start_time: Mapped[dt.time] = mapped_column(
        Time, Computed(_local("starts_at", "time"), persisted=True)
    )
    end_time: Mapped[dt.time | None] = mapped_column(
        Time, Computed(_local("ends_at", "time"), persisted=True)
    )

    location: Mapped[str | None] = mapped_column(Text)
    is_virtual: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    event_url: Mapped[str | None] = mapped_column(Text)
    meeting_link: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )

    source_uid: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    first_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', "
            "coalesce(event_name,'') || ' ' || "
            "coalesce(description,'') || ' ' || "
            "coalesce(location,''))",
            persisted=True,
        ),
    )

    calendar: Mapped[Calendar | None] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_events_starts_at", "starts_at"),
        Index("ix_events_event_date", "event_date", "starts_at"),
        Index("ix_events_calendar_id", "calendar_id"),
        Index("ix_events_source_uid", "calendar_id", "source_uid"),
        Index("ix_events_tags", "tags", postgresql_using="gin"),
        Index("ix_events_search", "search_vector", postgresql_using="gin"),
        Index(
            "ix_events_location_trgm",
            "location",
            postgresql_using="gin",
            postgresql_ops={"location": "gin_trgm_ops"},
        ),
        Index(
            "ix_events_active_upcoming",
            "starts_at",
            postgresql_where=text("status = 'active'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_name!r} @ {self.starts_at.isoformat()}>"
