"""Regression coverage for the Almanac adapter, built from a trimmed real page
(almanac.upenn.edu/at-penn-calendar, 2026-09-07): panels grouped by category, each
event a `<p>` whose bold day-of-month is only present on the first event of a day
and carries forward for the rest, with an italic title and free-text detail after.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from penn_events.adapters.almanac_adapter import AlmanacAdapter
from penn_events.core.models import RawRecord

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _record() -> RawRecord:
    payload = (FIXTURES / "almanac_sample.html").read_text()
    return RawRecord(format="html", url="https://almanac.upenn.edu/at-penn-calendar", payload=payload)


def test_subsection_labels_and_image_only_paragraphs_are_skipped(ctx):
    events = {e.event_name: e for e in AlmanacAdapter().adapt(_record(), ctx)}
    # "Morris Arboretum & Gardens" (bold, non-digit, no <i>) and the register-link
    # and bare-<img> paragraphs carry no title and must not become events.
    assert "Morris Arboretum & Gardens" not in events
    assert len(events) == 4


def test_day_carries_forward_and_time_is_extracted(ctx):
    events = {e.event_name: e for e in AlmanacAdapter().adapt(_record(), ctx)}
    sense = events["SENSE-sational Friday: Sensory Celebration"]
    assert sense.starts_at == dt.datetime(2026, 9, 4, 15, 0, tzinfo=dt.timezone.utc)  # 11am EDT
    assert sense.all_day is False

    storytime = events["September Storytime"]
    # Its own <p> has no <b> day marker at all -- day 16 carries from the header text.
    assert storytime.starts_at.astimezone(dt.timezone(dt.timedelta(hours=-4))).day == 16


def test_no_parseable_time_falls_back_to_all_day(ctx):
    events = {e.event_name: e for e in AlmanacAdapter().adapt(_record(), ctx)}
    railway = events["Magic Railway Weekend"]
    assert railway.all_day is True
    assert railway.starts_at.astimezone(dt.timezone(dt.timedelta(hours=-4))).date() == dt.date(2026, 9, 5)
    # The nested <i>Also September 6</i> must not override the real title.
    assert "Also September" not in railway.event_name


def test_full_detail_text_preserved_in_description_not_split(ctx):
    events = {e.event_name: e for e in AlmanacAdapter().adapt(_record(), ctx)}
    music = events["Music in the Pavilion: Duo Sapientia"]
    assert "Duo Sapientia" in music.description
    assert "Van Pelt Library" in music.description
    assert "Penn Libraries" in music.description
    assert music.event_url == "https://libcal.library.upenn.edu/event/17306877"
    assert music.tags == ["Music"]
