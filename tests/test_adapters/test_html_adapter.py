"""Regression coverage for the declarative HTML/CSS adapter.

Unlike the format-driven adapters, this one is configured per-site (see
penn_events/feeders/html_css.py) -- the test builds the same HtmlCssConfig a real
master.yaml block would produce and points it at a saved listing page fixture that
mirrors a typical Drupal/WordPress teaser markup.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from penn_events.adapters.html_adapter import HtmlCssAdapter, _first_range_token
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


def test_starts_time_field_is_recombined_with_a_date_only_starts_at(ctx):
    """Penn Today/Annenberg-style cards: a date-only element plus a separate
    'start-end' time range elsewhere in the card -- the adapter must recombine
    them and take only the range's start for the time-of-day."""
    config = HtmlCssConfig(
        list_url="https://example.upenn.edu/events/",
        item="article.event-teaser-split",
        fields={
            "event_name": FieldSelector(css="h3 a", attr="text"),
            "starts_at": FieldSelector(css=".event-date", attr="text"),
            "starts_time": FieldSelector(css=".event-time", attr="text"),
        },
    )
    events = {e.event_name: e for e in HtmlCssAdapter(config).adapt(_record(), ctx)}
    split = events["Split Date/Time Card"]
    assert split.starts_at == dt.datetime(2026, 9, 20, 18, 0, tzinfo=dt.timezone.utc)  # 2pm EDT


def test_first_range_token_splits_on_en_dash_and_em_dash_too():
    # CEET's markup uses an en dash ('3:00 pm – 4:00 pm'), not a hyphen --
    # confirmed live, 2026-09-07.
    assert _first_range_token("3:00 pm – 4:00 pm") == "3:00 pm"
    assert _first_range_token("3:00 pm — 4:00 pm") == "3:00 pm"
    assert _first_range_token("12:00pm-1:00pm") == "12:00pm"


def test_first_range_token_splits_on_the_word_to_as_well():
    # Penn Alumni's iModules markup spells the range out as "6:30 PM to 11:30 PM" --
    # no dash at all. Confirmed live, 2026-09-07: fuzzy-parsing the unsplit string
    # silently picked the *end* time (11:30 PM), not the start.
    assert _first_range_token("6:30 PM to 11:30 PM") == "6:30 PM"
