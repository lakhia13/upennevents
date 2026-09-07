"""Expose the registry's school_division on api.events.

The frontend's category taxonomy was guessing school affiliation from event
tags, which don't reliably encode it. calendars.school_division is the
authoritative source (from penn-calendars.csv, joined via events.calendar_id,
which is set on every active event) -- expose it directly instead.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # CREATE OR REPLACE VIEW may only append columns at the end of the SELECT
    # list -- it errors if an existing column's name/position/type changes --
    # so school_division goes last, not next to calendar_id where it reads
    # more naturally.
    conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW api.events AS
            SELECT
                e.id, e.event_name, e.host, e.source, e.source_calendar_name,
                e.calendar_id, e.starts_at, e.ends_at, e.all_day, e.event_date,
                e.start_time, e.end_time, e.location, e.is_virtual,
                e.event_url, e.meeting_link, e.description, e.tags,
                e.search_vector, e.first_seen_at, e.last_seen_at, e.updated_at,
                c.school_division
            FROM public.events e
            LEFT JOIN public.calendars c ON c.id = e.calendar_id
            WHERE e.status = 'active'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            """
            CREATE OR REPLACE VIEW api.events AS
            SELECT
                id, event_name, host, source, source_calendar_name, calendar_id,
                starts_at, ends_at, all_day, event_date, start_time, end_time,
                location, is_virtual, event_url, meeting_link, description, tags,
                search_vector, first_seen_at, last_seen_at, updated_at
            FROM public.events
            WHERE status = 'active'
            """
        )
    )
