"""Regression coverage for the TEC adapter, built from a real API response.

`tec_sample.json` was captured live from events.engineering.upenn.edu and
deliberately kept as two events: one with `venue` as a normal object, and one
("MSE Open House Featuring DuPont") where TEC returns `venue` as a *list* of
venue objects instead -- the shape that crashed `run-all` in production with
`AttributeError: 'list' object has no attribute 'get'` before the adapter was
fixed to normalize venue through `as_list()`.
"""
from __future__ import annotations

import json
from pathlib import Path

from penn_events.adapters.tec_adapter import TecAdapter
from penn_events.core.models import RawRecord

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _record() -> RawRecord:
    payload = json.loads((FIXTURES / "tec_sample.json").read_text())
    return RawRecord(format="json", url="https://events.engineering.upenn.edu/wp-json/...", payload=payload)


def test_single_venue_dict(ctx):
    events = list(TecAdapter().adapt(_record(), ctx))
    dict_venue_events = [e for e in events if e.source_uid == "23169"]
    assert len(dict_venue_events) == 1
    assert dict_venue_events[0].location  # a real address string, not empty


def test_list_of_venues_does_not_crash_and_joins_locations(ctx):
    """The event that previously raised AttributeError must now adapt cleanly."""
    events = list(TecAdapter().adapt(_record(), ctx))
    list_venue_events = [e for e in events if e.source_uid == "23629"]
    assert len(list_venue_events) == 1

    location = list_venue_events[0].location
    assert location is not None
    # Both venues from the list should be represented, joined rather than dropped.
    assert "Levine Hall" in location
    assert "Quain Courtyard" in location
