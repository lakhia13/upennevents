"""Which kind of Postgres this migration chain is running against.

The chain has to apply cleanly to two very different targets: a vanilla Postgres
(docker-compose, local dev) where it owns role creation outright, and a hosted
Supabase project where `authenticator`, `anon` and friends already exist and are
managed by the platform. Rewriting Supabase's `authenticator` password would take
its own PostgREST offline, so the distinction is load-bearing, not cosmetic.
"""
from __future__ import annotations

import os

from sqlalchemy import text
from sqlalchemy.engine import Connection

LOCAL_ANON_ROLE = "web_anon"
SUPABASE_ANON_ROLE = "anon"

# Postgres can't bind an identifier as a query parameter, so role names reach
# GRANT statements by interpolation. Keeping the set of possible values closed is
# what makes that safe.
_ALLOWED_ANON_ROLES = frozenset({LOCAL_ANON_ROLE, SUPABASE_ANON_ROLE})


class TargetError(RuntimeError):
    """Raised when the deployment target can't be determined safely."""


def is_supabase() -> bool:
    return os.environ.get("DB_TARGET", "local").strip().lower() == "supabase"


def anon_role() -> str:
    """The role anonymous PostgREST requests run as on this target."""
    role = SUPABASE_ANON_ROLE if is_supabase() else LOCAL_ANON_ROLE
    if role not in _ALLOWED_ANON_ROLES:  # unreachable today; guards future edits
        raise TargetError(f"refusing to interpolate role name {role!r}")
    return role


def assert_target_is_explicit(conn: Connection) -> None:
    """Refuse to run the role-management path against a platform that owns roles.

    DB_TARGET defaults to "local" so an unset environment keeps doing exactly what
    it has always done. The one case that default gets wrong is a Supabase project
    where someone forgot the flag -- and there the local path would ALTER a role
    the platform owns. Both `anon` and `authenticator` already existing is that
    platform's signature, so stop and say so rather than guess either way.
    """
    if is_supabase():
        return
    managed = conn.execute(
        text(
            "SELECT count(*) FROM pg_roles WHERE rolname IN ('anon', 'authenticator')"
        )
    ).scalar_one()
    if managed == 2:
        raise TargetError(
            "This database already has both 'anon' and 'authenticator' roles, which "
            "means it is almost certainly a managed Supabase project -- but DB_TARGET "
            "is not set to 'supabase'. Continuing would ALTER a role the platform "
            "owns and could take its API offline. Set DB_TARGET=supabase and re-run."
        )
