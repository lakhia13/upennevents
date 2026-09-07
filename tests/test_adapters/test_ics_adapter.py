"""Adapter tests run directly against saved payloads -- no network, no feeder."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from penn_events.adapters.ics_adapter import IcsAdapter
from penn_events.core.errors import AdaptError
from penn_events.core.models import RawRecord

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _record(name: str) -> RawRecord:
    payload = (FIXTURES / name).read_text()
    return RawRecord(format="ics", url=f"https://example.upenn.edu/{name}", payload=payload)


def test_real_vpul_payload_parses_floating_local_times(ctx):
    events = list(IcsAdapter().adapt(_record("vpul_sample.ics"), ctx))
    assert len(events) == 2

    first = events[0]
    assert first.event_name == "PWC Undergraduate Open House"
    assert first.source_uid == "5796-vpul-calendar@upenn.edu"
    # DTSTART:20260908T120000 is floating -- resolved against ctx.timezone (America/New_York,
    # EDT = UTC-4 in September) and converted to UTC.
    assert first.starts_at == dt.datetime(2026, 9, 8, 16, 0, tzinfo=dt.timezone.utc)
    assert first.ends_at == dt.datetime(2026, 9, 8, 20, 0, tzinfo=dt.timezone.utc)
    assert "Penn Women" in first.location
    assert "merch giveaways" in first.description


def test_all_day_event_uses_inclusive_end_date(ctx):
    events = {e.event_name: e for e in IcsAdapter().adapt(_record("synthetic.ics"), ctx)}
    symposium = events["All-Day Symposium"]

    assert symposium.all_day is True
    # DTEND;VALUE=DATE:20260912 is exclusive per RFC 5545; the adapter steps it
    # back one day so a 2-day event reads as ending on the 11th, not the 12th.
    assert symposium.starts_at.date() == dt.date(2026, 9, 10)
    assert symposium.ends_at.date() == dt.date(2026, 9, 11)


def test_rrule_expands_and_respects_exdate(ctx):
    events = [
        e for e in IcsAdapter().adapt(_record("synthetic.ics"), ctx) if e.event_name == "Weekly Lab Meeting"
    ]
    # COUNT=4 minus the one EXDATE-excluded occurrence.
    assert len(events) == 3
    start_dates = sorted(e.starts_at.date() for e in events)
    assert dt.date(2026, 9, 8) not in start_dates  # excluded by EXDATE
    assert start_dates == [dt.date(2026, 9, 1), dt.date(2026, 9, 15), dt.date(2026, 9, 22)]
    # Each occurrence gets its own source_uid so the repository treats them as
    # distinct events rather than colliding on dedupe_key.
    assert len({e.source_uid for e in events}) == 3


def test_cancelled_status_is_preserved(ctx):
    events = {e.event_name: e for e in IcsAdapter().adapt(_record("synthetic.ics"), ctx)}
    assert events["Cancelled Talk"].status == "cancelled"


def test_truncated_feed_recovers_complete_events_and_drops_the_partial_one(ctx):
    """Modeled on a real, reproducible truncation seen live on Penn Law's LiveWhale
    feed: no `END:VCALENDAR`, and the last `VEVENT` cut off mid-field. Everything
    before the cut is well-formed and should not be lost.
    """
    events = {e.event_name: e for e in IcsAdapter().adapt(_record("truncated_sample.ics"), ctx)}
    assert set(events) == {"Sentencing Makeup Class", "Lambda Halloween"}


def test_feed_with_no_recoverable_events_still_raises(ctx):
    record = RawRecord(format="ics", url="https://example.upenn.edu/garbage.ics", payload="not ics at all")
    with pytest.raises(AdaptError):
        list(IcsAdapter().adapt(record, ctx))
