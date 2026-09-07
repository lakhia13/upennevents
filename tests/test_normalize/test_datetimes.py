from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from penn_events.normalize.datetimes import (
    ensure_aware,
    expand_recurrence,
    is_within_horizon,
    parse_datetime,
)


def test_ensure_aware_attaches_configured_zone_then_converts_to_utc():
    floating = dt.datetime(2026, 7, 1, 9, 0)  # EDT, UTC-4
    result = ensure_aware(floating, "America/New_York")
    assert result == dt.datetime(2026, 7, 1, 13, 0, tzinfo=dt.timezone.utc)


def test_ensure_aware_respects_dst_boundary():
    # 2026-01-15 is EST (UTC-5): 9am local -> 14:00 UTC.
    # 2026-07-01 is EDT (UTC-4): 9am local -> 13:00 UTC.
    # Getting this wrong (e.g. hardcoding one offset) would make one of these fail.
    winter = ensure_aware(dt.datetime(2026, 1, 15, 9, 0), "America/New_York")
    summer = ensure_aware(dt.datetime(2026, 7, 1, 9, 0), "America/New_York")
    assert winter.hour == 14
    assert summer.hour == 13


def test_parse_datetime_handles_ordinal_suffixes_and_fuzzy_text():
    result = parse_datetime("March 5th, 2026 4:00pm", "America/New_York")
    assert result is not None
    assert result.astimezone(ZoneInfo("America/New_York")).hour == 16


def test_parse_datetime_handles_unix_epoch_string_from_html_datetime_attrs():
    # Real shape from Penn GSE's Drupal event listing: <time datetime="1788998400">.
    # dateutil.parser used to read the 10-digit string as a year and raise.
    result = parse_datetime("1788998400", "America/New_York")
    assert result == dt.datetime(2026, 9, 10, 0, 0, tzinfo=dt.timezone.utc)


def test_parse_datetime_returns_none_for_garbage():
    assert parse_datetime("not a date", "America/New_York") is None
    assert parse_datetime("", "America/New_York") is None
    assert parse_datetime(None, "America/New_York") is None


def test_is_within_horizon_bounds_correctly():
    now = dt.datetime.now(dt.timezone.utc)
    assert is_within_horizon(now + dt.timedelta(days=30), days=180) is True
    assert is_within_horizon(now + dt.timedelta(days=400), days=180) is False
    assert is_within_horizon(now - dt.timedelta(days=2), days=180, past_days=1) is False


def test_expand_recurrence_caps_at_horizon_and_skips_exdate():
    start = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)
    until = dt.datetime(2026, 1, 31, tzinfo=dt.timezone.utc)
    occurrences = expand_recurrence(
        start,
        "FREQ=WEEKLY;COUNT=10",  # would run past `until` without the bound
        until=until,
        exdates=[dt.datetime(2026, 1, 8, 12, 0, tzinfo=dt.timezone.utc)],
    )
    assert all(o <= until for o in occurrences)
    assert dt.datetime(2026, 1, 8, 12, 0, tzinfo=dt.timezone.utc) not in occurrences
    assert start in occurrences


def test_expand_recurrence_falls_back_to_single_occurrence_on_bad_rrule():
    start = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.timezone.utc)
    occurrences = expand_recurrence(start, "NOT A VALID RRULE", until=start + dt.timedelta(days=1))
    assert occurrences == [start]
