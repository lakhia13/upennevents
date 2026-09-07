"""Extracts schema.org `Event` objects from embedded JSON-LD `<script>` blocks."""
from __future__ import annotations

import json
import logging
import re

from penn_events.core.interfaces import Adapter
from penn_events.core.models import FeedContext, NormalizedEvent, RawRecord
from penn_events.normalize.datetimes import parse_datetime

from .base import absolute_url, as_list

log = logging.getLogger(__name__)

_SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _iter_event_nodes(document: object):
    """JSON-LD nests events under `@graph`, plain arrays, or a bare object."""
    for node in as_list(document.get("@graph")) if isinstance(document, dict) else as_list(document):
        node_type = node.get("@type") if isinstance(node, dict) else None
        types = as_list(node_type)
        if any(str(t).lower() == "event" for t in types):
            yield node


class JsonLdAdapter(Adapter):
    def adapt(self, record: RawRecord, ctx: FeedContext):
        for block in _SCRIPT_RE.findall(record.payload):
            try:
                document = json.loads(block.strip())
            except json.JSONDecodeError:
                continue
            for node in _iter_event_nodes(document):
                event = self._one(node, ctx, record)
                if event is not None:
                    yield event

    @staticmethod
    def _one(node: dict, ctx: FeedContext, record: RawRecord) -> NormalizedEvent | None:
        starts_at = parse_datetime(node.get("startDate"), ctx.timezone)
        if starts_at is None:
            return None
        ends_at = parse_datetime(node.get("endDate"), ctx.timezone)

        place = node.get("location")
        location = None
        if isinstance(place, dict):
            address = place.get("address")
            if isinstance(address, dict):
                address = ", ".join(
                    filter(None, [address.get("streetAddress"), address.get("addressLocality")])
                )
            location = place.get("name") or (address if isinstance(address, str) else None)
        elif isinstance(place, str):
            location = place

        organizer = node.get("organizer")
        host = organizer.get("name") if isinstance(organizer, dict) else organizer

        event_url = absolute_url(record.url, node.get("url"))
        attendance = str(node.get("eventAttendanceMode") or "")

        return NormalizedEvent(
            event_name=node.get("name") or "Untitled event",
            host=host,
            source=ctx.source,
            starts_at=starts_at,
            ends_at=ends_at,
            location=location,
            is_virtual="online" in attendance.lower(),
            event_url=event_url,
            description=node.get("description"),
            source_uid=node.get("@id") or event_url,
            raw={"source_url": record.url},
        )
