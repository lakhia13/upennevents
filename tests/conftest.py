"""Shared fixtures. No test in this suite hits the network or a real database."""
from __future__ import annotations

import pytest

from penn_events.core.models import FeedContext


@pytest.fixture
def ctx() -> FeedContext:
    return FeedContext(
        feeder_id="test-feeder",
        source="test:example.upenn.edu",
        host="Test School",
        source_calendar_name="Test Calendar",
        timezone="America/New_York",
        horizon_days=180,
    )
