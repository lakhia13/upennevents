"""Regression coverage for the JSON-LD adapter.

jsonld_sample.html has three <script type="application/ld+json"> blocks: a real
@graph (one WebPage node that must be filtered out, plus three real Events covering
the three location shapes the adapter branches on), one block that isn't valid JSON
at all, and one bare array containing an Event with no startDate. The malformed
block and the dateless event must be skipped without breaking extraction of the
real events.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from penn_events.adapters.jsonld_adapter import JsonLdAdapter
from penn_events.core.models import RawRecord

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _record() -> RawRecord:
    payload = (FIXTURES / "jsonld_sample.html").read_text()
    return RawRecord(format="html", url="https://example.upenn.edu/events/", payload=payload)


def test_extracts_only_real_events_skipping_non_event_nodes_and_malformed_blocks(ctx):
    events = {e.event_name: e for e in JsonLdAdapter().adapt(_record(), ctx)}
    # WebPage node excluded, malformed script skipped, dateless event skipped --
    # exactly the three well-formed Event nodes should come through.
    assert set(events) == {
        "Robotics Seminar: Soft Actuators",
        "Virtual Town Hall",
        "CBE Seminar: Polymer Interfaces",
    }


def test_location_prefers_place_name_over_address_when_both_present(ctx):
    events = {e.event_name: e for e in JsonLdAdapter().adapt(_record(), ctx)}
    seminar = events["Robotics Seminar: Soft Actuators"]
    assert seminar.location == "Towne Building, Room 100"
    assert seminar.host == "Mechanical Engineering and Applied Mechanics"
    assert seminar.is_virtual is False
    assert seminar.starts_at == dt.datetime(2026, 9, 15, 18, 0, tzinfo=dt.timezone.utc)
    assert seminar.ends_at == dt.datetime(2026, 9, 15, 19, 30, tzinfo=dt.timezone.utc)


def test_location_falls_back_to_joined_address_when_place_has_no_name(ctx):
    events = {e.event_name: e for e in JsonLdAdapter().adapt(_record(), ctx)}
    cbe = events["CBE Seminar: Polymer Interfaces"]
    assert cbe.location == "220 S 33rd St, Towne Building, Philadelphia"
    # Relative url resolved against the page url, since it has no site scheme.
    assert cbe.event_url == "https://example.upenn.edu/events/cbe-seminar/"


def test_bare_string_location_and_organizer_and_online_mode_detected(ctx):
    events = {e.event_name: e for e in JsonLdAdapter().adapt(_record(), ctx)}
    town_hall = events["Virtual Town Hall"]
    assert town_hall.location == "Zoom"
    assert town_hall.host == "Office of the Provost"
    assert town_hall.is_virtual is True


def test_sportsevent_type_is_recognized_as_an_event(ctx):
    """SIDEARM's team-schedule pages (pennathletics.com) emit a bare array of
    `@type: "SportsEvent"` nodes with no plain "Event" node anywhere -- a same-as-
    "event" check alone would drop every game silently.
    """
    payload = (FIXTURES / "jsonld_sidearm_sample.html").read_text()
    record = RawRecord(
        format="html", url="https://pennathletics.com/sports/football/schedule", payload=payload
    )
    events = {e.event_name: e for e in JsonLdAdapter().adapt(record, ctx)}
    assert set(events) == {
        "University of Pennsylvania At Bucknell ",
        "University of Pennsylvania Vs Lehigh ",
    }
    away_game = events["University of Pennsylvania At Bucknell "]
    assert away_game.starts_at == dt.datetime(2026, 9, 19, 19, 0, tzinfo=dt.timezone.utc)
    assert away_game.location == "Lewisburg, Pa."
    home_game = events["University of Pennsylvania Vs Lehigh "]
    assert home_game.location == "Franklin Field"
