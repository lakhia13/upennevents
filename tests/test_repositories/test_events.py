from __future__ import annotations

import datetime as dt

from penn_events.core.models import NormalizedEvent
from penn_events.db.repositories.events import EventRepository
from penn_events.normalize.dedupe import content_hash, dedupe_key


def _finished_event(ctx, **overrides) -> NormalizedEvent:
    fields = dict(
        event_name="Repository Test Event",
        source="test:example.upenn.edu",
        starts_at=dt.datetime(2026, 3, 5, 16, 0, tzinfo=dt.timezone.utc),
        location="Houston Hall",
        tags=["seminar"],
    )
    fields.update(overrides)
    event = NormalizedEvent(**fields)
    return event.model_copy(
        update={"dedupe_key": dedupe_key(event, ctx), "content_hash": content_hash(event)}
    )


def test_upsert_many_inserts_then_leaves_unchanged_events_alone(session, ctx):
    repo = EventRepository(session)
    event = _finished_event(ctx)

    first = repo.upsert_many([event])
    assert (first.inserted, first.updated, first.unchanged) == (1, 0, 0)

    second = repo.upsert_many([event])
    assert (second.inserted, second.updated, second.unchanged) == (0, 0, 1)

    assert repo.count() == 1


def test_upsert_many_updates_when_content_changes(session, ctx):
    repo = EventRepository(session)
    event = _finished_event(ctx)
    repo.upsert_many([event])

    moved = _finished_event(ctx, location="New Location")
    # Same dedupe_key (same title/start/scope), different content_hash.
    assert moved.dedupe_key == event.dedupe_key
    assert moved.content_hash != event.content_hash

    stats = repo.upsert_many([moved])
    assert (stats.inserted, stats.updated, stats.unchanged) == (0, 1, 0)

    stored = repo.get_by_dedupe_key(event.dedupe_key)
    assert stored.location == "New Location"


def test_generated_columns_derive_from_starts_at_in_local_time(session, ctx):
    repo = EventRepository(session)
    # 2026-03-08 04:30 UTC is 2026-03-07 23:30 EST (before the spring DST jump).
    event = _finished_event(ctx, starts_at=dt.datetime(2026, 3, 8, 4, 30, tzinfo=dt.timezone.utc))
    repo.upsert_many([event])

    stored = repo.get_by_dedupe_key(event.dedupe_key)
    assert stored.event_date == dt.date(2026, 3, 7)
    assert stored.start_time == dt.time(23, 30)


def test_mark_absent_as_removed_retires_events_outside_the_current_feed(session, ctx):
    repo = EventRepository(session)
    kept = _finished_event(ctx, event_name="Still Published")
    gone = _finished_event(ctx, event_name="No Longer Published")
    repo.upsert_many([kept, gone])

    window_start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    window_end = dt.datetime(2026, 12, 31, tzinfo=dt.timezone.utc)
    removed = repo.mark_absent_as_removed(
        ctx.calendar_id, ctx.source, [kept.dedupe_key], window_start, window_end
    )
    assert removed == 1

    assert repo.get_by_dedupe_key(kept.dedupe_key).status == "active"
    assert repo.get_by_dedupe_key(gone.dedupe_key).status == "removed"


def test_in_batch_duplicate_dedupe_keys_do_not_error(session, ctx):
    """Two records from the same feed resolving to the same identity must collapse
    to one row, not trip Postgres's "cannot affect row a second time" error."""
    repo = EventRepository(session)
    event = _finished_event(ctx)
    duplicate = event.model_copy(update={"description": "a later duplicate in the same feed"})

    stats = repo.upsert_many([event, duplicate])
    assert stats.total == 1
    assert repo.count() == 1
