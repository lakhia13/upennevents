"""Deny-by-default RLS on the raw tables, so only api.events is ever readable.

Second layer behind the hosting platform's "which schemas are exposed" setting.
`events` and `calendars` live in `public`, and a hosted PostgREST (Supabase's
included) exposes `public` by default -- which would serve the columns
api.events exists to hide: raw, dedupe_key, content_hash, source_uid, status.
Restricting exposed schemas to `api` is the primary control; this is what holds
if that setting is ever changed back.

Enabling RLS with no policies denies every non-owner by default. It does NOT
break reads through api.events: a view is security-definer unless declared
otherwise, so it executes as its owner -- the migration role, which also owns
these tables -- and RLS is not enforced against a table's owner without FORCE
ROW LEVEL SECURITY.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-07
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("events", "calendars")


def upgrade() -> None:
    conn = op.get_bind()
    for table in TABLES:
        conn.execute(text(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY"))


def downgrade() -> None:
    conn = op.get_bind()
    for table in TABLES:
        conn.execute(text(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY"))
