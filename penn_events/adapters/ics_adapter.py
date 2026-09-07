"""Maps RFC 5545 VEVENT components onto `NormalizedEvent`.

Handles the three things that make ICS unforgiving: `VALUE=DATE` all-day events,
floating (timezone-less) local times, and `RRULE` recurrence -- expansion is
bounded by the feeder's configured horizon so a yearly-forever meeting does not
generate decades of rows.
"""
from __future__ import annotations

import datetime as dt
import logging

from icalendar import Calendar as IcsCalendar

from penn_events.core.errors import AdaptError
from penn_events.core.interfaces import Adapter
from penn_events.core.models import FeedContext, NormalizedEvent, RawRecord
from penn_events.normalize.datetimes import ensure_aware, expand_recurrence, horizon

from .base import absolute_url

log = logging.getLogger(__name__)


def _text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


class IcsAdapter(Adapter):
    def adapt(self, record: RawRecord, ctx: FeedContext):
        try:
            calendar = IcsCalendar.from_ical(record.payload)
        except (ValueError, TypeError) as exc:
            calendar = self._repair_truncated(record.payload, exc, ctx)

        _, window_end = horizon(ctx.horizon_days)

        for component in calendar.walk("VEVENT"):
            yield from self._events_for(component, ctx, record, window_end)

    @staticmethod
    def _repair_truncated(payload: str, exc: Exception, ctx: FeedContext) -> IcsCalendar:
        """Recover a feed that was cut off mid-transfer rather than dropping it whole.

        Seen live on Penn Law's LiveWhale feed (2026-09-07): the response is missing
        `END:VCALENDAR` and its last `VEVENT` is cut mid-field, reproducibly across
        retries and cache-busting -- an upstream CDN caching bug, not a transient
        network blip. Everything before the cut is well-formed RFC 5545, so trim back
        to the last complete `END:VEVENT` and close the document there instead of
        losing every event in the feed over one bad trailing record.
        """
        if "END:VCALENDAR" in payload:
            raise AdaptError(f"{ctx.feeder_id}: not a valid ICS document ({exc})") from exc
        cutoff = payload.rfind("END:VEVENT")
        if cutoff == -1:
            raise AdaptError(f"{ctx.feeder_id}: not a valid ICS document ({exc})") from exc
        repaired = payload[: cutoff + len("END:VEVENT")] + "\r\nEND:VCALENDAR\r\n"
        try:
            calendar = IcsCalendar.from_ical(repaired)
        except (ValueError, TypeError):
            raise AdaptError(f"{ctx.feeder_id}: not a valid ICS document ({exc})") from exc
        log.warning("%s: ICS feed was truncated mid-transfer; recovered events up to the cut", ctx.feeder_id)
        return calendar

    def _events_for(self, component, ctx: FeedContext, record: RawRecord, window_end: dt.datetime):
        dtstart_prop = component.get("dtstart")
        if dtstart_prop is None:
            return

        raw_start = dtstart_prop.dt
        all_day = not isinstance(raw_start, dt.datetime)
        starts_at = self._resolve(raw_start, ctx.timezone)

        dtend_prop = component.get("dtend")
        ends_at = self._resolve(dtend_prop.dt, ctx.timezone) if dtend_prop else None
        if all_day and ends_at is not None:
            # DTEND on an all-day VEVENT is exclusive per RFC 5545 (a one-day event
            # has DTEND = DTSTART + 1 day); step it back so it reads as inclusive.
            ends_at -= dt.timedelta(days=1)
            if ends_at < starts_at:
                ends_at = starts_at

        uid = _text(component.get("uid"))
        title = _text(component.get("summary")) or "Untitled event"
        description = _text(component.get("description"))
        location = _text(component.get("location"))
        url = absolute_url(ctx.base_url, _text(component.get("url")))
        status = "cancelled" if _text(component.get("status")) == "CANCELLED" else "active"

        base = NormalizedEvent(
            event_name=title,
            source=ctx.source,
            starts_at=starts_at,
            ends_at=ends_at,
            all_day=all_day,
            location=location,
            event_url=url,
            description=description,
            source_uid=uid,
            status=status,
            raw={"uid": uid, "source_url": record.url},
        )

        rrule_prop = component.get("rrule")
        if rrule_prop is None:
            yield base
            return

        exdates: list[dt.datetime] = []
        for exdate_prop in component.get("exdate", []) if isinstance(component.get("exdate"), list) else (
            [component.get("exdate")] if component.get("exdate") else []
        ):
            for value in getattr(exdate_prop, "dts", []):
                exdates.append(self._resolve(value.dt, ctx.timezone))

        duration = (ends_at - starts_at) if ends_at else None
        occurrences = expand_recurrence(
            starts_at, rrule_prop.to_ical().decode(), until=window_end, exdates=exdates
        )
        for index, occurrence in enumerate(occurrences):
            occurrence_end = occurrence + duration if duration else None
            occurrence_uid = f"{uid}#{index}" if uid else None
            yield base.model_copy(
                update={
                    "starts_at": occurrence,
                    "ends_at": occurrence_end,
                    "source_uid": occurrence_uid,
                }
            )

    @staticmethod
    def _resolve(value: object, tz: str) -> dt.datetime:
        if isinstance(value, dt.datetime):
            return ensure_aware(value, tz)
        if isinstance(value, dt.date):
            return ensure_aware(dt.datetime.combine(value, dt.time.min), tz)
        raise AdaptError(f"unrecognized ICS date value: {value!r}")
