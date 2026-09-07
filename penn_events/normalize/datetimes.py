"""Timezone and recurrence handling.

Every source lies about time in a different way: LiveWhale emits floating local
times, ICS all-day events use exclusive DTEND, TEC hands back ISO strings with an
offset, HTML pages give you "Thursday, March 5 at 4:00pm".  Everything is resolved
to an aware UTC datetime here so the rest of the pipeline never thinks about it.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Iterable
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser
from dateutil import rrule as rrule_module

log = logging.getLogger(__name__)

DEFAULT_TZ = "America/New_York"
MAX_OCCURRENCES = 400  # hard stop so a malformed RRULE cannot expand forever


def zone(name: str | None = None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TZ)
    except Exception:
        log.warning("unknown timezone %r, falling back to %s", name, DEFAULT_TZ)
        return ZoneInfo(DEFAULT_TZ)


def ensure_aware(value: dt.datetime, tz: str | None = None) -> dt.datetime:
    """Attach the calendar's timezone to a floating datetime, then convert to UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=zone(tz))
    return value.astimezone(dt.timezone.utc)


def from_date(value: dt.date, tz: str | None = None) -> dt.datetime:
    """Midnight local time on a bare date -- used for all-day events."""
    return ensure_aware(dt.datetime.combine(value, dt.time.min), tz)


def parse_datetime(value: object, tz: str | None = None) -> dt.datetime | None:
    """Best-effort parse of whatever a source calls a date.

    Handles datetimes, dates, epoch seconds and free text.  Returns None rather than
    raising, because one unparseable event should not fail a whole feed.
    """
    if value is None or value == "":
        return None
    if isinstance(value, dt.datetime):
        return ensure_aware(value, tz)
    if isinstance(value, dt.date):
        return from_date(value, tz)
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(float(value), dt.timezone.utc)

    text_value = str(value).strip()
    if not text_value:
        return None
    # Strip ordinal suffixes ("March 5th") that dateutil chokes on.
    text_value = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text_value, flags=re.I)
    try:
        return ensure_aware(date_parser.parse(text_value, fuzzy=True), tz)
    except (ValueError, OverflowError, TypeError):
        log.debug("could not parse datetime from %r", value)
        return None


def horizon(days: int, *, past_days: int = 1) -> tuple[dt.datetime, dt.datetime]:
    """The window a feeder is responsible for, as (start, end) in UTC."""
    now = dt.datetime.now(dt.timezone.utc)
    return now - dt.timedelta(days=past_days), now + dt.timedelta(days=days)


def is_within_horizon(when: dt.datetime, days: int, *, past_days: int = 365) -> bool:
    """Reject dates far enough out to be parser noise (a stray "2029" in body text)."""
    start, end = horizon(days, past_days=past_days)
    return start <= when <= end


def expand_recurrence(
    start: dt.datetime,
    rrule_text: str,
    *,
    until: dt.datetime,
    exdates: Iterable[dt.datetime] = (),
) -> list[dt.datetime]:
    """Expand an RFC 5545 RRULE, bounded by the feeder's horizon.

    Returns the start datetimes of every occurrence including the first.  A rule we
    cannot parse degrades to the single original occurrence rather than failing.
    """
    try:
        rule = rrule_module.rrulestr(rrule_text, dtstart=start, forceset=True)
    except Exception as exc:
        log.debug("unparseable RRULE %r (%s); keeping single occurrence", rrule_text, exc)
        return [start]

    excluded = {e.astimezone(dt.timezone.utc) for e in exdates}
    occurrences: list[dt.datetime] = []
    for occurrence in rule:
        if occurrence > until or len(occurrences) >= MAX_OCCURRENCES:
            break
        occurrence = ensure_aware(occurrence)
        if occurrence not in excluded:
            occurrences.append(occurrence)
    return occurrences or [start]
