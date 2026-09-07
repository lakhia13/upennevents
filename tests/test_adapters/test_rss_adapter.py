"""Regression coverage for the RSS adapter, built from SAS's real feed shape
(www.sas.upenn.edu/events/rss.xml): each <item> carries a <sdo:Event> block with the
actual event start/end, which must win over <pubDate> (when the item was posted).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from penn_events.adapters.rss_adapter import RssAdapter
from penn_events.core.models import RawRecord

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _record() -> RawRecord:
    payload = (FIXTURES / "rss_sample.xml").read_text()
    return RawRecord(format="xml", url="https://example.upenn.edu/events/rss.xml", payload=payload)


def test_prefers_sdo_event_startdate_over_pubdate(ctx):
    events = {e.event_name: e for e in RssAdapter().adapt(_record(), ctx)}
    lecture = events["60-Second Lectures | Political Neutrality and Sociology"]
    # sdo:startDate is 2026-09-09T16:00:00Z; pubDate (Aug 17) must be ignored.
    assert lecture.starts_at == dt.datetime(2026, 9, 9, 16, 0, tzinfo=dt.timezone.utc)
    assert lecture.ends_at is None  # <sdo:endDate/> is empty
    assert lecture.source_uid == "96f2e733-7e30-4bad-81ee-9a94ce0db64d"
    assert lecture.tags == ["Arts & Culture", "Lecture"]


def test_content_encoded_html_is_stripped_to_plain_text(ctx):
    events = {e.event_name: e for e in RssAdapter().adapt(_record(), ctx)}
    lecture = events["60-Second Lectures | Political Neutrality and Sociology"]
    assert lecture.description is not None
    assert "<h4>" not in lecture.description
    assert "The 60-Second Lectures are back!" in lecture.description
    assert "Melissa J. Wilde" in lecture.description


def test_endDate_populated_when_present(ctx):
    events = {e.event_name: e for e in RssAdapter().adapt(_record(), ctx)}
    republic = events["Model Republic: Why the American Founders Loved Ancient Carthage"]
    assert republic.starts_at == dt.datetime(2026, 9, 10, 22, 0, tzinfo=dt.timezone.utc)
    assert republic.ends_at == dt.datetime(2026, 9, 11, 0, 0, tzinfo=dt.timezone.utc)


def test_falls_back_to_pubdate_when_no_structured_event_block(ctx):
    events = {e.event_name: e for e in RssAdapter().adapt(_record(), ctx)}
    plain = events["Plain Item With No Structured Event Data"]
    assert plain.starts_at == dt.datetime(2026, 8, 27, 9, 0, tzinfo=dt.timezone.utc)
    assert plain.source_uid == "plain-item-guid"
