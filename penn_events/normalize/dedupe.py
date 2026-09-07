"""Event identity.

`dedupe_key` is the single upsert target for the whole platform.  When a source
gives a stable id (an ICS UID, a TEC post id, a SIDEARM game id) that id defines
identity; otherwise identity falls back to title + start time within the calendar.

Using one key rather than two competing unique constraints means `upsert_many` is a
single `ON CONFLICT` statement and can never hit "cannot affect row a second time"
against a constraint it did not target.

`content_hash` is separate and covers the *content*: it is how the repository knows
whether a re-scrape actually changed anything.
"""
from __future__ import annotations

import hashlib

from penn_events.core.models import FeedContext, NormalizedEvent

from .text import title_key


def _digest(*parts: object) -> str:
    joined = "\x1f".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def dedupe_key(event: NormalizedEvent, ctx: FeedContext) -> str:
    """Stable identity for one event within its calendar."""
    scope = str(ctx.calendar_id) if ctx.calendar_id else ctx.source
    if event.source_uid:
        return _digest("uid", scope, event.source_uid)
    return _digest(
        "fallback",
        scope,
        title_key(event.event_name),
        event.starts_at.isoformat(timespec="minutes"),
    )


def content_hash(event: NormalizedEvent) -> str:
    """Changes whenever anything a reader would notice changes."""
    return _digest(
        event.event_name,
        event.starts_at.isoformat(),
        event.ends_at.isoformat() if event.ends_at else None,
        event.all_day,
        event.location,
        event.event_url,
        event.meeting_link,
        event.description,
        ",".join(sorted(event.tags)),
        event.host,
        event.status,
    )
