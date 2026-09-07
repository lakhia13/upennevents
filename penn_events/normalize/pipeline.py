"""The cross-cutting normalization stage.

Adapters do format-specific field mapping and nothing else; everything that must
happen identically for all 511 calendars happens here, exactly once.
"""
from __future__ import annotations

import logging
from typing import Iterable

from penn_events.core.models import FeedContext, NormalizedEvent

from . import datetimes, location, text
from .dedupe import content_hash, dedupe_key
from .tagger import Tagger

log = logging.getLogger(__name__)

MAX_TITLE = 500


class Normalizer:
    """Applies cleanup, tagging and hashing to raw adapter output."""

    def __init__(self, tagger: Tagger | None = None) -> None:
        self.tagger = tagger or Tagger()

    def normalize(
        self, events: Iterable[NormalizedEvent], ctx: FeedContext
    ) -> list[NormalizedEvent]:
        normalized: list[NormalizedEvent] = []
        dropped = 0

        for event in events:
            finished = self.normalize_one(event, ctx)
            if finished is None:
                dropped += 1
                continue
            normalized.append(finished)

        if dropped:
            log.info("%s: dropped %d unusable events", ctx.feeder_id, dropped)
        return normalized

    def normalize_one(self, event: NormalizedEvent, ctx: FeedContext) -> NormalizedEvent | None:
        """Returns the finished event, or None if it cannot be stored."""
        name = text.clean(event.event_name, max_length=MAX_TITLE)
        if not name or event.starts_at is None:
            return None

        # A date far outside the feeder's horizon is almost always a parsing artefact.
        if not datetimes.is_within_horizon(event.starts_at, ctx.horizon_days):
            log.debug("%s: %r out of horizon at %s", ctx.feeder_id, name, event.starts_at)
            return None

        description = text.clean_description(event.description)
        place = location.clean_location(text.clean(event.location))
        meeting_link = event.meeting_link or location.extract_meeting_link(
            event.location, description, event.event_url
        )

        ends_at = event.ends_at
        if ends_at is not None and ends_at < event.starts_at:
            ends_at = None  # nonsense range; better absent than wrong

        tags = self.tagger.tags_for(
            title=name,
            description=description,
            location=place,
            inherited=[*ctx.registry_tags, *ctx.static_tags, *event.tags],
        )

        finished = event.model_copy(
            update={
                "event_name": name,
                "description": description,
                "location": place,
                "ends_at": ends_at,
                "meeting_link": meeting_link,
                "is_virtual": location.looks_virtual(place, description, meeting_link),
                "tags": tags,
                "host": event.host or ctx.host,
                "source": event.source or ctx.source,
                "source_calendar_name": event.source_calendar_name or ctx.source_calendar_name,
                "calendar_id": event.calendar_id or ctx.calendar_id,
            }
        )
        return finished.model_copy(
            update={
                "dedupe_key": dedupe_key(finished, ctx),
                "content_hash": content_hash(finished),
            }
        )
