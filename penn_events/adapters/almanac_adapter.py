"""Maps Almanac's category-accordion page onto `NormalizedEvent`.

Each panel is one category (Talks, Music, ...); inside it every event is one
`<p>`: a bold day-of-month present only on the first event of a given day (and
carried forward for the rest, the same convention a printed digest uses), an
italic title, then free-text detail -- a description/speaker, a time, a
location, often a registration link, and a "(Department)" credit -- with no
further markup to split that detail on reliably. Rather than guess a
description/location split that could silently attribute the wrong text to the
wrong field, only the day and a best-effort time are pulled out as structured
fields; everything else stays intact, unsplit, in `description`.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from bs4 import BeautifulSoup

from penn_events.core.interfaces import Adapter
from penn_events.core.models import FeedContext, NormalizedEvent, RawRecord
from penn_events.normalize.datetimes import ensure_aware

from .base import absolute_url

log = logging.getLogger(__name__)

_TIME_RE = re.compile(
    r"\b(noon|midnight|\d{1,2}(?::\d{2})?\s*(?:a\.m\.|p\.m\.|am|pm))", re.IGNORECASE
)


def _parse_time(text: str) -> dt.time | None:
    match = _TIME_RE.search(text)
    if not match:
        return None
    token = match.group(1).lower()
    if token == "noon":
        return dt.time(12, 0)
    if token == "midnight":
        return dt.time(0, 0)
    token = token.replace(".", "").replace(" ", "")
    for fmt in ("%I:%M%p", "%I%p"):
        try:
            return dt.datetime.strptime(token, fmt).time()
        except ValueError:
            continue
    return None


class AlmanacAdapter(Adapter):
    def adapt(self, record: RawRecord, ctx: FeedContext):
        soup = BeautifulSoup(record.payload, "lxml")
        month_label = soup.select_one(".calendar-module header h1 small")
        month_start = self._parse_month(month_label.get_text(strip=True)) if month_label else None
        if month_start is None:
            log.warning("%s: could not find the 'Month YYYY' header on the page; skipping", ctx.feeder_id)
            return

        for panel in soup.select(".panel-group .panel"):
            heading = panel.select_one(".panel-heading a")
            category = heading.get_text(strip=True) if heading else None
            body = panel.select_one(".panel-body")
            if body is None:
                continue
            yield from self._events_for_panel(body, category, month_start, ctx, record)

    @staticmethod
    def _parse_month(label: str) -> dt.date | None:
        try:
            return dt.datetime.strptime(label, "%B %Y").date()
        except ValueError:
            return None

    @staticmethod
    def _events_for_panel(body, category, month_start, ctx, record):
        current_day: int | None = None
        for p in body.find_all("p", recursive=False):
            bold = p.find("b")
            if bold is not None:
                digits = bold.get_text(strip=True)
                if digits.isdigit():
                    current_day = int(digits)
            title_el = p.find("i")
            if title_el is None or current_day is None:
                continue
            title = title_el.get_text(strip=True)
            if not title:
                continue

            try:
                event_date = month_start.replace(day=current_day)
            except ValueError:
                log.debug(
                    "%s: day %d out of range for %s; skipping", ctx.feeder_id, current_day, month_start
                )
                continue

            detail_text = p.get_text(" ", strip=True)
            event_time = _parse_time(detail_text)
            all_day = event_time is None
            starts_at = ensure_aware(
                dt.datetime.combine(event_date, event_time or dt.time.min), ctx.timezone
            )

            link = p.find("a")
            event_url = absolute_url(record.url, link.get("href")) if link else None

            yield NormalizedEvent(
                event_name=title,
                source=ctx.source,
                starts_at=starts_at,
                all_day=all_day,
                event_url=event_url,
                description=detail_text,
                tags=[category] if category else [],
                raw={"category": category, "source_url": record.url},
            )
