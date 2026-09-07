from __future__ import annotations

import datetime as dt
import uuid

from penn_events.core.models import FeedContext, NormalizedEvent
from penn_events.normalize.dedupe import content_hash, dedupe_key


def _event(**overrides) -> NormalizedEvent:
    defaults = dict(
        event_name="Test Talk",
        source="test:example.upenn.edu",
        starts_at=dt.datetime(2026, 3, 5, 16, 0, tzinfo=dt.timezone.utc),
    )
    defaults.update(overrides)
    return NormalizedEvent(**defaults)


def test_dedupe_key_prefers_source_uid_over_title(ctx):
    a = _event(source_uid="abc123", event_name="Original Title")
    b = _event(source_uid="abc123", event_name="Title Changed Later")
    assert dedupe_key(a, ctx) == dedupe_key(b, ctx)


def test_dedupe_key_falls_back_to_title_and_start_when_no_uid(ctx):
    a = _event(event_name="Weekly Meeting")
    b = _event(event_name="weekly   MEETING")  # casing/whitespace should not matter
    assert dedupe_key(a, ctx) == dedupe_key(b, ctx)


def test_dedupe_key_differs_across_calendars_for_the_same_uid(ctx):
    other_ctx = ctx.model_copy(update={"calendar_id": uuid.uuid4()})
    a = _event(source_uid="shared-uid")
    assert dedupe_key(a, ctx) != dedupe_key(a, other_ctx)


def test_content_hash_changes_when_a_reader_visible_field_changes():
    base = _event()
    moved = _event(location="New Room")
    assert content_hash(base) != content_hash(moved)


def test_content_hash_stable_across_identical_events():
    assert content_hash(_event()) == content_hash(_event())
