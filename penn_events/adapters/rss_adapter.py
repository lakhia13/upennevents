"""Maps RSS `<item>` elements to NormalizedEvent.

Namespaced elements (content:encoded, sdo:startDate, ...) are looked up by their
local name only (`find("startDate")`, not `find("sdo:startDate")`) -- BeautifulSoup's
lxml-xml parser matches both, and the bare form reads better and doesn't assume a
particular prefix, which isn't guaranteed to be spelled the same on every feed.
"""
from __future__ import annotations

from bs4 import BeautifulSoup
from bs4.element import Tag

from penn_events.core.interfaces import Adapter
from penn_events.core.models import FeedContext, NormalizedEvent, RawRecord
from penn_events.normalize.datetimes import parse_datetime


def _text(tag: Tag | None) -> str | None:
    if tag is None:
        return None
    value = tag.get_text(strip=True)
    return value or None


def _clean_html(raw: str | None) -> str | None:
    """content:encoded is HTML-as-text (from CDATA) -- strip it to plain text."""
    if not raw:
        return None
    text = BeautifulSoup(raw, "lxml").get_text(separator=" ", strip=True)
    return text or None


class RssAdapter(Adapter):
    def adapt(self, record: RawRecord, ctx: FeedContext):
        soup = BeautifulSoup(record.payload, "xml")
        for item in soup.find_all("item"):
            event = self._one(item, ctx)
            if event is not None:
                yield event

    @staticmethod
    def _one(item: Tag, ctx: FeedContext) -> NormalizedEvent | None:
        name = _text(item.find("title"))
        if not name:
            return None

        # Prefer the embedded schema.org event block's startDate/endDate over
        # pubDate, which is only when the RSS item itself was published.
        event_node = item.find("Event")
        starts_raw = _text(event_node.find("startDate")) if event_node else None
        starts_at = parse_datetime(starts_raw, ctx.timezone) if starts_raw else None
        if starts_at is None:
            starts_at = parse_datetime(_text(item.find("pubDate")), ctx.timezone)
        if starts_at is None:
            return None

        ends_raw = _text(event_node.find("endDate")) if event_node else None
        ends_at = parse_datetime(ends_raw, ctx.timezone) if ends_raw else None

        link = _text(item.find("link"))
        guid_tag = item.find("guid")
        guid = _text(guid_tag) if guid_tag is not None else None

        description = _clean_html(_text(item.find("encoded"))) or _text(item.find("description"))
        tags = [t for t in (_text(c) for c in item.find_all("category")) if t]

        return NormalizedEvent(
            event_name=name,
            source=ctx.source,
            starts_at=starts_at,
            ends_at=ends_at,
            event_url=link,
            description=description,
            tags=tags,
            source_uid=guid or link,
            raw={"source_url": link} if link else {},
        )
