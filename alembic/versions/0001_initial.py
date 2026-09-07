"""Initial schema: calendars (registry) and events (unified store).

Revision ID: 0001
Revises:
Create Date: 2026-09-06
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DISPLAY_TZ = "America/New_York"


def upgrade() -> None:
    # gen_random_uuid() is built into Postgres core since v13; pg_trgm is not,
    # and is required for the fuzzy location search index below.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "calendars",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("unit", sa.Text()),
        sa.Column("school_division", sa.Text()),
        sa.Column("category", sa.Text()),
        sa.Column("calendar_name", sa.Text()),
        sa.Column("calendar_url", sa.Text(), nullable=False),
        sa.Column("platform_cms", sa.Text()),
        sa.Column("how_content_is_rendered", sa.Text()),
        sa.Column("feed_api_endpoint", sa.Text()),
        sa.Column("best_fetch_method", sa.Text()),
        sa.Column("confidence", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("calendar_url", name="uq_calendars_calendar_url"),
    )
    op.create_index("ix_calendars_school_division", "calendars", ["school_division"])
    op.create_index("ix_calendars_platform_cms", "calendars", ["platform_cms"])

    op.create_table(
        "events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("host", sa.Text()),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_calendar_name", sa.Text()),
        sa.Column(
            "calendar_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calendars.id", ondelete="SET NULL"),
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "event_date",
            sa.Date(),
            sa.Computed(
                f"((starts_at AT TIME ZONE '{DISPLAY_TZ}')::date)", persisted=True
            ),
        ),
        sa.Column(
            "start_time",
            sa.Time(),
            sa.Computed(
                f"((starts_at AT TIME ZONE '{DISPLAY_TZ}')::time)", persisted=True
            ),
        ),
        sa.Column(
            "end_time",
            sa.Time(),
            sa.Computed(
                f"((ends_at AT TIME ZONE '{DISPLAY_TZ}')::time)", persisted=True
            ),
        ),
        sa.Column("location", sa.Text()),
        sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("event_url", sa.Text()),
        sa.Column("meeting_link", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("source_uid", sa.Text()),
        sa.Column("dedupe_key", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("raw", postgresql.JSONB()),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', "
                "coalesce(event_name,'') || ' ' || "
                "coalesce(description,'') || ' ' || "
                "coalesce(location,''))",
                persisted=True,
            ),
        ),
        sa.UniqueConstraint("dedupe_key", name="uq_events_dedupe_key"),
    )
    op.create_index("ix_events_starts_at", "events", ["starts_at"])
    op.create_index("ix_events_event_date", "events", ["event_date", "starts_at"])
    op.create_index("ix_events_calendar_id", "events", ["calendar_id"])
    op.create_index("ix_events_source_uid", "events", ["calendar_id", "source_uid"])
    op.create_index("ix_events_tags", "events", ["tags"], postgresql_using="gin")
    op.create_index("ix_events_search", "events", ["search_vector"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX ix_events_location_trgm ON events "
        "USING gin (location gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_events_active_upcoming ON events (starts_at) "
        "WHERE status = 'active'"
    )


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("calendars")
