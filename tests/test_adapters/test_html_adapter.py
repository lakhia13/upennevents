"""Regression coverage for the declarative HTML/CSS adapter.

Unlike the format-driven adapters, this one is configured per-site (see
penn_events/feeders/html_css.py) -- the test builds the same HtmlCssConfig a real
master.yaml block would produce and points it at a saved listing page fixture that
mirrors a typical Drupal/WordPress teaser markup.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from penn_events.adapters.html_adapter import HtmlCssAdapter
from penn_events.core.models import RawRecord
from penn_events.feeders.html_css import FieldSelector, HtmlCssConfig

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _record() -> RawRecord:
    payload = (FIXTURES / "html_sample.html").read_text()
    return RawRecord(format="html", url="https://example.upenn.edu/events/", payload=payload)


def _config() -> HtmlCssConfig:
    return HtmlCssConfig(
        list_url="https://example.upenn.edu/events/",
        item="article.event-teaser",
        fields={
            "event_name": FieldSelector(css="h3 a", attr="text"),
            "event_url": FieldSelector(css="h3 a", attr="href"),
            "starts_at": FieldSelector(css="time", attr="datetime"),
            "location": FieldSelector(css=".event-location", attr="text"),
            "tags": FieldSelector(css=".event-tags .tag", attr="text", multiple=True),
        },
    )


def test_extracts_events_and_skips_items_with_no_parseable_start_time(ctx):
    events = {e.event_name: e for e in HtmlCssAdapter(_config()).adapt(_record(), ctx)}
    # "Date TBD Event" has no <time> element at all -- must be skipped, not crash.
    assert set(events) == {"MSE Open House", "Faculty Colloquium"}


def test_relative_url_resolved_against_base_url(ctx):
    events = {e.event_name: e for e in HtmlCssAdapter(_config()).adapt(_record(), ctx)}
    open_house = events["MSE Open House"]
    assert open_house.event_url == "https://example.upenn.edu/events/mse-open-house/"
    assert open_house.location == "LRSM Auditorium"
    assert open_house.starts_at == dt.datetime(2026, 9, 18, 17, 0, tzinfo=dt.timezone.utc)


def test_absolute_url_left_unchanged(ctx):
    events = {e.event_name: e for e in HtmlCssAdapter(_config()).adapt(_record(), ctx)}
    colloquium = events["Faculty Colloquium"]
    assert colloquium.event_url == "https://example.upenn.edu/events/faculty-colloquium/"


def test_multiple_field_collects_every_matching_tag(ctx):
    events = {e.event_name: e for e in HtmlCssAdapter(_config()).adapt(_record(), ctx)}
    open_house = events["MSE Open House"]
    assert open_house.tags == ["Open House", "Undergraduate"]
    assert events["Faculty Colloquium"].tags == ["Colloquium"]
