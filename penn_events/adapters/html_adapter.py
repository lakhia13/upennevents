"""Extracts events from a list page using the CSS selectors configured in YAML.

Unlike the other adapters, this one is instantiated with its feeder's config
(`HtmlCssFeeder.adapter()` passes it in) because the selectors are per-site, not
per-format. Everything cross-cutting (cleanup, timezone, tagging) still happens
later in `normalize.pipeline`, so this stays a thin field extractor.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from bs4.element import Tag

from penn_events.core.interfaces import Adapter
from penn_events.core.models import FeedContext, NormalizedEvent, RawRecord
from penn_events.normalize.datetimes import parse_datetime

from .base import absolute_url

if TYPE_CHECKING:
    from penn_events.feeders.html_css import FieldSelector, HtmlCssConfig

log = logging.getLogger(__name__)


def _extract(tag: Tag, field: "FieldSelector") -> list[str]:
    elements = tag.select(field.css) if field.css else [tag]
    if not field.multiple:
        elements = elements[:1]

    values: list[str] = []
    for element in elements:
        if field.attr == "text":
            value = element.get_text(separator=" ", strip=True)
        else:
            value = element.get(field.attr)
        if value:
            values.append(value if isinstance(value, str) else str(value))
    return values


class HtmlCssAdapter(Adapter):
    def __init__(self, config: "HtmlCssConfig") -> None:
        self.config = config

    def adapt(self, record: RawRecord, ctx: FeedContext):
        soup = BeautifulSoup(record.payload, "lxml")
        base_url = self.config.resolved_base_url()

        for item in soup.select(self.config.item):
            event = self._one(item, ctx, record, base_url)
            if event is not None:
                yield event

    def _one(self, item: Tag, ctx: FeedContext, record: RawRecord, base_url: str) -> NormalizedEvent | None:
        fields = self.config.fields
        values = {name: _extract(item, selector) for name, selector in fields.items()}

        name = (values.get("event_name") or [None])[0]
        starts_raw = (values.get("starts_at") or [None])[0]
        if not name or not starts_raw:
            return None
        starts_at = parse_datetime(starts_raw, ctx.timezone)
        if starts_at is None:
            log.debug("%s: could not parse start time %r for %r", ctx.feeder_id, starts_raw, name)
            return None

        ends_raw = (values.get("ends_at") or [None])[0]
        ends_at = parse_datetime(ends_raw, ctx.timezone) if ends_raw else None

        event_url = absolute_url(base_url, (values.get("event_url") or [None])[0])
        location = (values.get("location") or [None])[0]
        description = (values.get("description") or [None])[0]
        tags = values.get("tags") or []

        return NormalizedEvent(
            event_name=name,
            source=ctx.source,
            starts_at=starts_at,
            ends_at=ends_at,
            location=location,
            event_url=event_url,
            description=description,
            tags=tags,
            source_uid=event_url,
            raw={"source_url": record.url},
        )
