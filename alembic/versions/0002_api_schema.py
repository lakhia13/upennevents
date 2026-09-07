"""PostgREST API layer: api.events read-only view + web_anon/authenticator roles.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06
"""
from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Local-dev placeholder, matching the "penn"/"penn" precedent already set in
# .env.example — production deployments must override this via the environment.
DEFAULT_AUTHENTICATOR_PASSWORD = "postgrest_dev_password"


def upgrade() -> None:
    conn = op.get_bind()
    pwd = os.environ.get(
        "POSTGREST_AUTHENTICATOR_PASSWORD", DEFAULT_AUTHENTICATOR_PASSWORD
    )
    # CREATE/ALTER ROLE ... PASSWORD takes a bare string literal (Sconst) in
    # Postgres's grammar, not an expression -- it cannot be a bind parameter
    # (attempting one raises "could not determine data type of parameter $1",
    # and PostgreSQL scans for $n placeholders even inside dollar-quoted DO
    # bodies). pwd comes from a trusted deployment env var, not user input;
    # single quotes are still escaped defensively before splicing it in.
    pwd_literal = pwd.replace("'", "''")

    # Roles are cluster-level and have no native "IF NOT EXISTS" -- guard with a
    # DO block so this migration is safe to run against a cluster that already
    # has them (e.g. a redeploy). web_anon carries no login of its own; every
    # anonymous PostgREST request runs as web_anon via SET ROLE from
    # authenticator, so its grants are the entire attack surface of the API.
    conn.execute(
        text(
            f"""
            DO $$
            BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'web_anon') THEN
                CREATE ROLE web_anon NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticator') THEN
                CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD '{pwd_literal}';
              ELSE
                ALTER ROLE authenticator WITH PASSWORD '{pwd_literal}';
              END IF;
            END
            $$;
            """
        )
    )
    conn.execute(text("GRANT web_anon TO authenticator"))

    conn.execute(text("CREATE SCHEMA IF NOT EXISTS api"))
    conn.execute(text("GRANT USAGE ON SCHEMA api TO web_anon"))

    # Deliberately excludes raw, dedupe_key, content_hash, source_uid and status
    # (filtered instead), and scopes to active events only -- these columns
    # never exist in the api schema, so no future grant can leak them.
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
    conn.execute(text("GRANT SELECT ON api.events TO web_anon"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP VIEW IF EXISTS api.events"))
    conn.execute(text("DROP SCHEMA IF EXISTS api"))
    conn.execute(text("REVOKE web_anon FROM authenticator"))
    # Roles intentionally left in place -- other objects/migrations may still
    # depend on them, and DROP ROLE with dependents would fail loudly anyway.
