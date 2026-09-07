"""PostgREST API layer: the api.events read-only view, and the role that reads it.

Which role that is depends on the target: a self-hosted Postgres gets a `web_anon`
role created here, while a managed platform (Supabase) already provides `anon` and
owns `authenticator` -- there we create and alter nothing, and only grant. See
penn_events/db/deploy_target.py; the target is explicit (DB_TARGET), never guessed.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06
"""
from __future__ import annotations

import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

from penn_events.db.deploy_target import (
    anon_role,
    assert_target_is_explicit,
    is_supabase,
)

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Local-dev placeholder, matching the "penn"/"penn" precedent already set in
# .env.example — production deployments must override this via the environment.
DEFAULT_AUTHENTICATOR_PASSWORD = "postgrest_dev_password"


def upgrade() -> None:
    conn = op.get_bind()
    assert_target_is_explicit(conn)
    # 'anon' on Supabase (platform-provided), 'web_anon' on a self-hosted
    # Postgres we create ourselves below. Validated against a closed allowlist,
    # because an identifier cannot be a bind parameter.
    role = anon_role()

    if is_supabase():
        # authenticator/anon already exist and belong to the platform. Creating
        # is unnecessary and ALTERing is actively dangerous: Supabase's own
        # PostgREST authenticates as `authenticator`, so rewriting its password
        # here would take the hosted API offline.
        pass
    else:
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

        # Roles are cluster-level and have no native "IF NOT EXISTS" -- guard
        # with a DO block so this migration is safe to run against a cluster that
        # already has them (e.g. a redeploy). web_anon carries no login of its
        # own; every anonymous PostgREST request runs as web_anon via SET ROLE
        # from authenticator, so its grants are the entire attack surface.
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
    conn.execute(text(f"GRANT USAGE ON SCHEMA api TO {role}"))

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
    conn.execute(text(f"GRANT SELECT ON api.events TO {role}"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP VIEW IF EXISTS api.events"))
    conn.execute(text("DROP SCHEMA IF EXISTS api"))
    if not is_supabase():
        conn.execute(text("REVOKE web_anon FROM authenticator"))
    # Roles intentionally left in place -- other objects/migrations may still
    # depend on them, and DROP ROLE with dependents would fail loudly anyway.
