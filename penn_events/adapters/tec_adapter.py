"""Maps a page of The Events Calendar's JSON API onto `NormalizedEvent`."""
from __future__ import annotations

import logging

from penn_events.core.interfaces import Adapter
from penn_events.core.models import FeedContext, NormalizedEvent, RawRecord
from penn_events.normalize.datetimes import parse_datetime

from .base import as_list, pluck

log = logging.getLogger(__name__)


class TecAdapter(Adapter):
    def adapt(self, record: RawRecord, ctx: FeedContext):
        events = record.payload.get("events") if isinstance(record.payload, dict) else None
        for item in events or []:
            event = self._one(item, ctx, record)
            if event is not None:
                yield event

    @staticmethod
    def _one(item: dict, ctx: FeedContext, record: RawRecord) -> NormalizedEvent | None:
        starts_at = parse_datetime(pluck(item, "utc_start_date", "start_date"), ctx.timezone)
        if starts_at is None:
            log.debug("%s: TEC event %r missing start date", ctx.feeder_id, item.get("title"))
            return None
        ends_at = parse_datetime(pluck(item, "utc_end_date", "end_date"), ctx.timezone)

        # TEC returns a single venue object, but an event with multiple venues
        # (e.g. a building tour) comes back as a *list* of them instead.
        venues = [v for v in as_list(item.get("venue")) if isinstance(v, dict)]
        location = "; ".join(
            ", ".join(p for p in (v.get("venue"), v.get("address"), v.get("city")) if p)
            for v in venues
            if v.get("venue") or v.get("address")
        ) or None

        organizer_names = [o.get("organizer") for o in as_list(item.get("organizer")) if isinstance(o, dict)]
        tags = [t.get("name") for t in as_list(item.get("tags")) if isinstance(t, dict) and t.get("name")]
        tags += [c.get("name") for c in as_list(item.get("categories")) if isinstance(c, dict) and c.get("name")]

        return NormalizedEvent(
            event_name=item.get("title") or "Untitled event",
            host=organizer_names[0] if organizer_names else None,
            source=ctx.source,
            starts_at=starts_at,
            ends_at=ends_at,
            all_day=bool(item.get("all_day")),
            location=location,
            event_url=item.get("url") or item.get("website"),
            description=item.get("description"),
            tags=tags,
            source_uid=str(item.get("id")) if item.get("id") is not None else None,
            raw={"id": item.get("id"), "source_url": record.url},
        )
