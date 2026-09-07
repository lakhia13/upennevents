"""Reads and writes for table 2, the unified event store.

One `INSERT ... ON CONFLICT DO UPDATE` per batch, keyed on `dedupe_key`.  The
conflict clause carries a `WHERE content_hash IS DISTINCT FROM excluded.content_hash`
guard so a re-scrape that finds nothing new performs no write at all -- which keeps
`updated_at` meaningful as "when this event last actually changed".

Insert-vs-update is counted with the `xmax = 0` trick: on a freshly inserted row
xmax is zero, on an updated one it is the current transaction id.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Iterable, Sequence
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert

from penn_events.core.models import NormalizedEvent, UpsertStats
from penn_events.db.models import Event

from .base import Repository

log = logging.getLogger(__name__)

# Everything except the primary key, the generated columns and first_seen_at.
_WRITABLE = (
    "event_name",
    "host",
    "source",
    "source_calendar_name",
    "calendar_id",
    "starts_at",
    "ends_at",
    "all_day",
    "location",
    "is_virtual",
    "event_url",
    "meeting_link",
    "description",
    "tags",
    "source_uid",
    "dedupe_key",
    "content_hash",
    "status",
    "raw",
)

BATCH_SIZE = 500


class EventRepository(Repository):
    def upsert_many(self, events: Sequence[NormalizedEvent]) -> UpsertStats:
        """Insert new events, update changed ones, leave unchanged ones untouched."""
        stats = UpsertStats()
        rows = self._to_rows(events)
        if not rows:
            return stats

        for start in range(0, len(rows), BATCH_SIZE):
            batch = rows[start : start + BATCH_SIZE]
            statement = insert(Event).values(batch)
            statement = statement.on_conflict_do_update(
                index_elements=[Event.dedupe_key],
                set_={
                    **{c: statement.excluded[c] for c in _WRITABLE if c != "dedupe_key"},
                    "last_seen_at": func.now(),
                    "updated_at": func.now(),
                },
                where=Event.content_hash.is_distinct_from(statement.excluded.content_hash),
            ).returning(text("(xmax = 0) AS is_insert"))

            touched = list(self.session.scalars(statement))
            stats.inserted += sum(1 for is_insert in touched if is_insert)
            stats.updated += sum(1 for is_insert in touched if not is_insert)
            stats.unchanged += len(batch) - len(touched)

        # Rows skipped by the WHERE guard still need their last_seen_at refreshed,
        # otherwise the deletion sweep below would eventually retire live events.
        self._touch_last_seen([row["dedupe_key"] for row in rows])
        return stats

    def mark_absent_as_removed(
        self,
        calendar_id: UUID | None,
        source: str,
        seen_keys: Iterable[str],
        window_start: dt.datetime,
        window_end: dt.datetime,
    ) -> int:
        """Retire events the source no longer publishes.

        Scoped to the date window that was actually refetched, so a feeder that only
        returns the next 30 days never retires events six months out.  Rows are
        flipped to `status='removed'` rather than deleted, keeping history intact.
        """
        seen = list(seen_keys)
        condition = (
            (Event.starts_at >= window_start)
            & (Event.starts_at <= window_end)
            & (Event.status == "active")
        )
        condition = condition & (
            Event.calendar_id == calendar_id if calendar_id is not None else Event.source == source
        )
        if seen:
            condition = condition & Event.dedupe_key.notin_(seen)

        result = self.session.execute(
            update(Event).where(condition).values(status="removed", updated_at=func.now())
        )
        removed = result.rowcount or 0
        if removed:
            log.info("retired %d events no longer published by %s", removed, source)
        return removed

    def get_by_dedupe_key(self, dedupe_key: str) -> Event | None:
        return self.session.scalar(select(Event).where(Event.dedupe_key == dedupe_key))

    def count(self, *, active_only: bool = False) -> int:
        statement = select(func.count()).select_from(Event)
        if active_only:
            statement = statement.where(Event.status == "active")
        return self.session.scalar(statement) or 0

    def upcoming(self, limit: int = 20) -> list[Event]:
        """Convenience read used by the CLI to eyeball a run's output."""
        return list(
            self.session.scalars(
                select(Event)
                .where(Event.status == "active", Event.starts_at >= func.now())
                .order_by(Event.starts_at)
                .limit(limit)
            )
        )

    def _touch_last_seen(self, dedupe_keys: Sequence[str]) -> None:
        for start in range(0, len(dedupe_keys), BATCH_SIZE):
            self.session.execute(
                update(Event)
                .where(Event.dedupe_key.in_(dedupe_keys[start : start + BATCH_SIZE]))
                .values(last_seen_at=func.now())
                .execution_options(synchronize_session=False)
            )

    @staticmethod
    def _to_rows(events: Sequence[NormalizedEvent]) -> list[dict]:
        """Project events onto writable columns, keeping the last of any in-batch dupes.

        Postgres refuses an ON CONFLICT statement that would touch the same row twice,
        so duplicates within a single feed must be collapsed before the insert.
        """
        by_key: dict[str, dict] = {}
        for event in events:
            row = event.model_dump(include=set(_WRITABLE))
            if not row.get("dedupe_key"):
                raise ValueError(f"event {event.event_name!r} has no dedupe_key; normalize it first")
            by_key[row["dedupe_key"]] = row
        return list(by_key.values())
